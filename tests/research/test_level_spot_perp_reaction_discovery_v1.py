"""LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1. Outcome-blind guards and feature identity."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research.level_spot_perp_reaction_discovery_v1 import constants as K
from scripts.research.level_spot_perp_reaction_discovery_v1.claim import (
    conjunction, route, specificity_pass, support_sensitive, year_stability,
)
from scripts.research.level_spot_perp_reaction_discovery_v1.evaluate import refuse_if_recorded
from scripts.research.level_spot_perp_reaction_discovery_v1.features import (
    log_return, perp_median, spot_features, window_imbalance,
)
from scripts.research.level_spot_perp_reaction_discovery_v1.inference import (
    bh_adjust, columns_for, drop_redundant, fit_matched, fit_rows, identical_columns,
)
from scripts.research.level_spot_perp_reaction_discovery_v1.spot import SpotSeries


def _row(i: int, feature: float, y: float, cluster: int) -> dict:
    return {
        "y": y,
        "END_POSITION_X": float((i % 5) - 2),
        "OTHER_VENUE_MEDIAN_MOVE": float((i * 2) % 5 - 2),
        "SPOT_ORIENTED_MOVE_15M": feature,
        "disp": float((i % 4) - 1),
        "family": "WEEK" if i % 7 == 0 else "DAY",
        "support": float((i // 2) % 2),
        "vol_tercile": (i // 3) % 3,
        "epoch": ("2020", "2021", "2022")[i % 3],
        "time_block": (i // 5) % 4,
        "cluster": cluster,
        "side": 1 if i % 2 == 0 else -1,
    }


def test_spot_identity_and_window_constants():
    text = "\n".join(path.read_text() for path in Path("scripts/research/level_spot_perp_reaction_discovery_v1").glob("*.py"))
    assert K.SPOT_DATASET_ID == "DH1_BINANCE_SPOT_BTCUSDT_5M_V0"
    assert K.SPOT_INSTRUMENT == "Binance spot BTCUSDT"
    assert K.SPOT_INTERVAL == "5m"
    assert "BTC-USDT-SWAP" not in text.split("OTHER_VENUES")[0]
    assert "mark-price-candles?" not in text
    assert "2026-01" not in text and "2025-01-02" not in text
    assert K.SURFACE_END_MS == 1735689600000
    assert K.EVENT_START_MS == 1585699200000 + 300_000
    assert K.REACTION_MS == 15 * 60_000
    assert K.LATE_START_OFFSET == 3 and K.LATE_STOP_OFFSET == 49
    assert K.CV1_NAME == "OTHER_VENUE_MEDIAN_MOVE"
    assert "late_label" not in Path("scripts/research/level_spot_perp_reaction_discovery_v1/preflight.py").read_text()


def test_spot_lookup_is_exact_and_refuses_2025():
    series = SpotSeries(
        np.asarray([1585699200000, 1585699500000]),
        np.asarray([10.0, 11.0]),
        np.asarray([100.0, 100.0]),
        np.asarray([60.0, 40.0]),
    )
    assert series.close_at(1585699200000) == 10.0
    assert series.close_at(1585699200000 + 60_000) is None
    assert series.flow_at(1585699800000) == (None, None)
    with pytest.raises(RuntimeError):
        SpotSeries(np.asarray([K.SURFACE_END_MS]), np.asarray([1.0]), np.asarray([1.0]), np.asarray([0.0]))


def test_no_forward_fill_and_orientations():
    series = SpotSeries(
        np.asarray([1585699200000, 1585699200000 + 600_000]),
        np.asarray([10.0, 12.0]),
        np.asarray([1.0, 1.0]),
        np.asarray([0.5, 0.5]),
    )
    assert log_return(series.close_at(1585699200000), series.close_at(1585699200000 + 300_000)) is None
    up = spot_features(math.log(1.1), 0.01, 0.02, 0.03, side=1, spot_imbalance=0.2, perp_imbalance=0.5)
    down = spot_features(math.log(1.1), 0.01, 0.02, 0.03, side=-1, spot_imbalance=0.2, perp_imbalance=0.5)
    assert up["SPOT_ORIENTED_MOVE_15M"] == pytest.approx(math.log(1.1))
    assert down["SPOT_ORIENTED_MOVE_15M"] == pytest.approx(-math.log(1.1))
    assert up["RELATIVE_SPOT_TAKER_PRESSURE_15M"] == pytest.approx(-0.3)
    assert down["RELATIVE_SPOT_TAKER_PRESSURE_15M"] == pytest.approx(0.3)
    assert perp_median((0.0, 0.10, 0.90)) == pytest.approx(0.10)
    excess = spot_features(0.05, 0.0, 0.10, 0.90, side=1, spot_imbalance=None, perp_imbalance=None)
    assert excess["SPOT_EXCESS_VS_PERP_COMPLEX"] == pytest.approx(0.05 - 0.10)
    assert excess["RELATIVE_SPOT_TAKER_PRESSURE_15M"] is None
    zero = window_imbalance([10.0, 10.0, 10.0], [5.0, 5.0, 5.0])
    assert zero == pytest.approx(0.0)
    assert window_imbalance([10.0, None, 10.0], [5.0, 5.0, 5.0]) is None
    assert window_imbalance([10.0, 0.0, 10.0], [5.0, 0.0, 5.0]) is None


def test_every_model_contains_endpoint_and_cv1():
    rows = [_row(i, 0.01 * ((i % 7) - 3), float(i % 2), i // 4) for i in range(80)]
    scales = {
        "END_POSITION_X": {"mean": 0.0, "sd": 1.0},
        "disp": {"mean": 0.0, "sd": 1.0},
        "OTHER_VENUE_MEDIAN_MOVE": {"mean": 0.0, "sd": 1.0},
        "SPOT_ORIENTED_MOVE_15M": {"mean": 0.0, "sd": 1.0},
    }
    base = fit_rows(rows, None, scales, draws=0)
    cand = fit_rows(rows, "SPOT_ORIENTED_MOVE_15M", scales, draws=0)
    assert "endpos_z" in base["columns"] and "cv1_z" in base["columns"]
    assert "endpos_z" in cand["columns"] and "cv1_z" in cand["columns"]
    assert "feature_z" in cand["columns"]
    assert base["n"] == cand["n"]
    assert base["includes_end_position"] and cand["includes_cv1"]


def test_redundancy_drops_the_later_feature():
    rows = []
    for i in range(30):
        rows.append({
            "SPOT_ORIENTED_MOVE_15M": float(i),
            "SPOT_EXCESS_VS_PERP_COMPLEX": float(i) * 1.01,
            "RELATIVE_SPOT_TAKER_PRESSURE_15M": float(i % 3),
        })
    dropped = drop_redundant(rows, K.FEATURES)
    assert dropped["retained"][0] == "SPOT_ORIENTED_MOVE_15M"
    assert any(item["feature"] == "SPOT_EXCESS_VS_PERP_COMPLEX" for item in dropped["dropped"])


def test_bh_and_year_rule():
    qs = bh_adjust([0.01, 0.04, 0.20])
    assert qs[0] <= qs[1] <= 0.10 or qs[0] <= 0.10
    epochs = [{"name": str(y), "n": 40, "coef": 0.05 if y != 2020 else -0.01} for y in range(2020, 2025)]
    assert year_stability(0.04, epochs)["pass"] is True
    flipped = [{"name": str(y), "n": 40, "coef": 0.05 if y % 2 == 0 else -0.05} for y in range(2020, 2025)]
    assert year_stability(0.04, flipped)["pass"] is False


def test_matched_models_share_columns_and_pairs():
    real, pseudo = [], []
    for i in range(40):
        real.append(_row(i, float((i * 3) % 7) - 3.0, float(i % 2), i // 5))
        other = _row(i + 3, float((i * 5) % 6) - 2.0, float((i + 1) % 2), i // 5)
        other["cluster"] = real[-1]["cluster"]
        pseudo.append(other)
    scales = {
        "END_POSITION_X": {"mean": 0.0, "sd": 1.0},
        "disp": {"mean": 0.0, "sd": 1.0},
        "OTHER_VENUE_MEDIAN_MOVE": {"mean": 0.0, "sd": 1.0},
        "SPOT_ORIENTED_MOVE_15M": {"mean": 0.0, "sd": 1.0},
    }
    columns = identical_columns(real, pseudo, "SPOT_ORIENTED_MOVE_15M", scales)
    assert columns[1:4] == ["endpos_z", "cv1_z", "feature_z"]
    pairs = [{"real": left, "pseudo": right} for left, right in zip(real, pseudo)]
    matched = fit_matched(pairs, "SPOT_ORIENTED_MOVE_15M", scales, draws=20, seed=7)
    assert matched["status"] == "ESTIMATED"
    assert matched["n_pairs"] == 40
    assert "feature_x_real" not in matched["columns"]
    assert matched["delta"] == pytest.approx(matched["beta_real"] - matched["beta_pseudo"])


def test_support_sensitive_route_blocks_interaction():
    assert support_sensitive(0.08, 0.001) is True
    assert support_sensitive(0.08, -0.02) is True
    assert support_sensitive(0.08, 0.05) is False
    matched = {"status": "ESTIMATED", "delta": -0.04, "delta_ci95": [-0.06, -0.02], "beta_real": 0.001}
    assert specificity_pass(matched, 0.08) is False
    features = [{
        "candidate_class": "GENERIC_SPOT_PERP_REACTION_CANDIDATE",
        "specificity_status": "SUPPORT_SENSITIVE",
        "statistical": True,
        "conjunction_pass": True,
        "ci95": [0.04, 0.10],
    }]
    assert route(features, n_resolved=500, history_ok=True, novelty_ok=True) == (
        "SPECIFICITY_NOT_ESTABLISHED_SUPPORT_SENSITIVE"
    )
    interaction = [{
        "candidate_class": "LEVEL_SPOT_PERP_INTERACTION_CANDIDATE",
        "specificity_status": "LEVEL_SPECIFIC",
        "statistical": True,
        "conjunction_pass": True,
        "ci95": [0.04, 0.10],
    }]
    assert route(interaction, n_resolved=500, history_ok=True, novelty_ok=True) == "LEVEL_SPOT_PERP_STRUCTURE_PRESENT"
    assert route([], n_resolved=1000, history_ok=True, novelty_ok=False) == "BLOCKED_REOPENING_SPOT_CONFIRMATION_CELL"


def test_conjunction_requires_both_baselines():
    cell = {
        "coef": 0.05, "ci95": [0.02, 0.08], "q": 0.01,
        "includes_end_position": True, "includes_cv1": False,
    }
    epochs = [{"name": str(y), "n": 40, "coef": 0.05} for y in range(2020, 2025)]
    got = conjunction(cell, epochs, [{"name": "omit", "n": 100, "coef": 0.04}] * 4,
                      [{"name": "DAY", "n": 80, "coef": 0.04}, {"name": "WEEK", "n": 40, "coef": 0.03}],
                      [{"name": "resistance", "n": 40, "coef": 0.04}, {"name": "support", "n": 40, "coef": 0.04}],
                      identity_artifact=False)
    assert "statistical" in got["failed"]


def test_rerun_refusal(tmp_path: Path):
    recorded = tmp_path / "RESULT.json"
    recorded.write_text("{}")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        refuse_if_recorded(recorded, tmp_path / "missing.md")


def test_columns_for_puts_cv1_before_the_spot_feature():
    rows = [_row(i, 0.0, 1.0, 1) for i in range(6)]
    cols = columns_for(rows, feature=True)
    assert cols[:4] == ["intercept", "endpos_z", "cv1_z", "feature_z"]
