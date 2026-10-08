"""Timing, early exclusion, reaction formulas, and the frozen estimator."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from beta.hist_series import Bars

from scripts.research.level_post_touch_reaction_discovery_v1 import constants as K
from scripts.research.level_post_touch_reaction_discovery_v1.analyze import _ready, attach_late, y_of
from scripts.research.level_post_touch_reaction_discovery_v1.claim import conjunction
from scripts.research.level_post_touch_reaction_discovery_v1.inference import bh_adjust, fit_rows
from scripts.research.level_post_touch_reaction_discovery_v1.late import late_label
from scripts.research.level_post_touch_reaction_discovery_v1.reactions import (
    early_status,
    end_position,
    oi_at,
    oi_reaction,
    reaction_features,
)

ROOT = Path(__file__).resolve().parents[2]
J = 20
ZONE_LOW = 100.0
ZONE_HIGH = 101.0
X = 0.01
BREAK_UP = ZONE_HIGH * (1.0 + X)
REJECT_DOWN = ZONE_LOW * (1.0 - X)


def _bars() -> Bars:
    n = 80
    close = np.full(n, 100.5)
    high = np.full(n, 100.8)
    low = np.full(n, 100.2)
    quote = np.full(n, 10.0)
    taker = np.full(n, 6.0)
    return Bars(
        t0=0,
        open=close.copy(),
        high=high,
        low=low,
        close=close,
        volume=np.full(n, 1.0),
        quote=quote,
        taker_buy_quote=taker,
        oi=np.full(n, np.nan),
    )


def _scales():
    flat = {"mean": 0.0, "sd": 1.0, "q33": -0.4, "q66": 0.4, "n": 10}
    return {
        "END_POSITION_X": dict(flat),
        "RELATIVE_ACTIVITY_15M": dict(flat),
        "disp": dict(flat),
        "rel_volume": dict(flat),
    }


def test_clocks_and_parent_end():
    assert K.REACTION_MS == 15 * 60 * 1000
    assert K.EARLY_START_OFFSET == 1 and K.EARLY_STOP_OFFSET == 3
    assert K.LATE_START_OFFSET == 3 and K.LATE_STOP_OFFSET == 49
    assert K.LATE_STOP_OFFSET == 1 + K.HORIZON
    assert K.EVENT_START_MS == K.OI_FIRST_AVAILABLE_MS
    assert K.EVENT_END.startswith("2025-01-01")
    text = (ROOT / "scripts/research/level_post_touch_reaction_discovery_v1/preflight.py").read_text()
    assert "late_label" not in text
    assert "LATE_RESOLVE" not in text


def test_touch_bar_is_not_a_resolution_and_early_cases():
    bars = _bars()
    bars.high[J] = BREAK_UP + 5
    bars.low[J] = REJECT_DOWN - 5
    assert early_status(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "UNRESOLVED"
    bars.high[J + 1] = BREAK_UP
    assert early_status(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "EARLY_BREAK"
    bars.high[J + 1] = 100.8
    bars.low[J + 2] = REJECT_DOWN
    assert early_status(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "EARLY_REJECT"
    bars.high[J + 1] = BREAK_UP
    bars.low[J + 1] = REJECT_DOWN
    assert early_status(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "EARLY_AMBIGUOUS"


def test_late_window_starts_at_j3_and_ends_at_j48():
    bars = _bars()
    bars.high[J + 3] = BREAK_UP
    assert early_status(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "UNRESOLVED"
    assert late_label(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "BREAK"
    bars.high[J + 3] = 100.8
    bars.low[J + 48] = REJECT_DOWN
    assert late_label(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "REJECT"
    bars.low[J + 48] = 100.2
    # The next bar is outside the original 4h end.
    bars.high[J + 49] = BREAK_UP + 10
    assert late_label(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "NEITHER"
    bars.high[J + 10] = BREAK_UP
    bars.low[J + 10] = REJECT_DOWN
    assert late_label(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "AMBIGUOUS"


def test_early_resolved_is_excluded_from_primary():
    bars = _bars()
    bars.high[J + 1] = BREAK_UP
    row = {
        "early_status": early_status(bars.high, bars.low, J, 1, ZONE_LOW, ZONE_HIGH, X),
        "j": J, "side": 1, "zone_low": ZONE_LOW, "zone_high": ZONE_HIGH, "x_primary": X,
        "END_POSITION_X": 0.2, "nuisance_ok": True, "outcome": "BREAK",
    }
    labeled = attach_late(bars, [row])[0]
    assert labeled["early_status"] == "EARLY_BREAK"
    assert labeled["outcome"] is None
    assert _ready(labeled, "END_POSITION_X", "LATE_RESOLVE_BY_4H", require_end=False) is None
    assert y_of("BREAK", "LATE_RESOLVE_BY_4H") == 1.0
    assert y_of("NEITHER", "LATE_RESOLVE_BY_4H") == 0.0
    assert y_of("AMBIGUOUS", "LATE_BREAK_GIVEN_RESOLVED") is None
    assert y_of("REJECT", "LATE_BREAK_GIVEN_RESOLVED") == 0.0


def test_r1_orientation_and_no_post_d_leak():
    assert math.isclose(end_position(ZONE_HIGH * (1.0 + X), 1, ZONE_LOW, ZONE_HIGH, X), 1.0)
    assert end_position(ZONE_HIGH, 1, ZONE_LOW, ZONE_HIGH, X) == 0.0
    below = end_position(ZONE_HIGH * 0.99, 1, ZONE_LOW, ZONE_HIGH, X)
    assert below is not None and below < 0.0
    assert math.isclose(end_position(ZONE_LOW * (1.0 - X), -1, ZONE_LOW, ZONE_HIGH, X), 1.0)
    assert end_position(ZONE_LOW, -1, ZONE_LOW, ZONE_HIGH, X) == 0.0
    above = end_position(ZONE_LOW * 1.01, -1, ZONE_LOW, ZONE_HIGH, X)
    assert above is not None and above < 0.0
    bars = _bars()
    got = reaction_features(J * K.BAR_MS, 0, bars.close, bars.quote, bars.taker_buy_quote,
                            1, ZONE_LOW, ZONE_HIGH, X, 0.0)
    bars.close[J + 3] = 10_000.0
    bars.quote[J + 3] = 10_000.0
    bars.taker_buy_quote[J + 3] = 9_000.0
    again = reaction_features(J * K.BAR_MS, 0, bars.close, bars.quote, bars.taker_buy_quote,
                              1, ZONE_LOW, ZONE_HIGH, X, 0.0)
    assert got == again


def test_activity_taker_and_change():
    bars = _bars()
    bars.quote[J - 12:J] = 4.0
    bars.quote[J:J + 3] = 12.0
    bars.taker_buy_quote[J:J + 3] = 9.0
    up = reaction_features(J * K.BAR_MS, 0, bars.close, bars.quote, bars.taker_buy_quote,
                           1, ZONE_LOW, ZONE_HIGH, X, 0.10)
    down = reaction_features(J * K.BAR_MS, 0, bars.close, bars.quote, bars.taker_buy_quote,
                             -1, ZONE_LOW, ZONE_HIGH, X, -0.20)
    assert math.isclose(up["RELATIVE_ACTIVITY_15M"], math.log(3.0))
    assert up["ORIENTED_TAKER_REACTION_15M"] > 0.0
    assert down["ORIENTED_TAKER_REACTION_15M"] < 0.0
    assert math.isclose(up["TAKER_CHANGE_VS_PRE"], up["ORIENTED_TAKER_REACTION_15M"] - 0.10)
    bars.quote[J - 12:J] = 0.0
    missing = reaction_features(J * K.BAR_MS, 0, bars.close, bars.quote, bars.taker_buy_quote,
                                1, ZONE_LOW, ZONE_HIGH, X, 0.10)
    assert missing["RELATIVE_ACTIVITY_15M"] is None


def test_oi_availability_and_staleness():
    t = 1_000_000_000
    step = K.BAR_MS
    avail = np.array(
        [t - 2 * step, t - step, t, t + step, t + 2 * step, t + 3 * step, t + 4 * step],
        dtype=np.int64,
    )
    values = np.array([8.0, 9.0, 10.0, 10.0, 10.0, 12.0, 100.0])
    assert oi_at(avail, values, t) == (t, 10.0)
    assert oi_at(avail, values, t + K.REACTION_MS) == (t + K.REACTION_MS, 12.0)
    change = oi_reaction(avail, values, t)
    assert change is not None and math.isclose(change, math.log(1.2))
    # Exact print at T missing: the previous native print is legal. Two periods back is not.
    gap = np.array([t - 2 * step, t - step, t + 3 * step], dtype=np.int64)
    assert oi_at(gap, np.array([9.0, 9.0, 12.0]), t) == (t - step, 9.0)
    assert oi_at(np.array([t - 2 * step]), np.array([9.0]), t) is None
    future = np.array([t, t + 4 * step], dtype=np.int64)
    assert oi_at(future, np.array([10.0, 20.0]), t + K.REACTION_MS) is None
    decreased = np.array([t, t + 3 * step], dtype=np.int64)
    got = oi_reaction(decreased, np.array([10.0, 5.0]), t)
    assert got is not None and got < 0.0


def test_scaling_fdr_and_week_bootstrap():
    rng = np.random.default_rng(11)
    rows = []
    for i in range(240):
        rows.append({
            "RELATIVE_ACTIVITY_15M": float(rng.normal()),
            "END_POSITION_X": float(rng.normal()),
            "disp": float(rng.normal()),
            "rel_volume": float(rng.normal()),
            "y": float(rng.integers(0, 2)),
            "family": ("DAY", "WEEK", "MONTH")[int(rng.integers(0, 3))],
            "support": float(rng.integers(0, 2)),
            "vol_tercile": int(rng.integers(0, 3)),
            "epoch": K.EPOCHS[int(rng.integers(0, 5))],
            "time_block": int(rng.integers(0, 4)),
            "cluster": int(i % 12),
            "side": 1 if i % 2 == 0 else -1,
            "early_status": "UNRESOLVED",
            "nuisance_ok": True,
        })
    cell = fit_rows(rows, "RELATIVE_ACTIVITY_15M", _scales(), end_position=True, draws=200, seed=3)
    assert cell["end_position_nuisance"] is True
    assert "endpos_z" in cell["columns"]
    assert cell["coef"] is not None and cell["bootstrap_valid"] >= 180
    own = fit_rows(rows, "END_POSITION_X", _scales(), end_position=True, draws=0, seed=1)
    assert own["end_position_nuisance"] is False
    assert "endpos_z" not in own["columns"]
    qs = bh_adjust([0.01, 0.04, 0.20, None])
    assert qs[0] <= qs[1] <= qs[2] <= qs[3]
    assert qs[0] <= 0.04


def test_epoch_clause_allows_one_eligible_flip():
    cell = {"coef": 0.04, "q": 0.05, "n": 400, "ci95": [0.01, 0.07]}
    epochs = [
        {"n": 80, "coef": 0.02},
        {"n": 80, "coef": 0.03},
        {"n": 80, "coef": 0.01},
        {"n": 80, "coef": 0.05},
        {"n": 80, "coef": -0.01},
    ]
    loyo = [{"n": 320, "coef": 0.03} for _ in range(5)]
    lofo = [{"n": 200, "coef": 0.02} for _ in range(3)]
    sides = [{"n": 200, "coef": 0.03}, {"n": 200, "coef": 0.02}]
    rule = conjunction(cell, epochs, loyo, lofo, sides)
    assert rule["pass"] is True
    epochs[3]["coef"] = -0.02
    assert "epochs" in conjunction(cell, epochs, loyo, lofo, sides)["failed"]


def test_surface_bounds_and_funding_constant():
    assert "2025" not in K.EVENT_START
    assert "2026" not in K.EVENT_END
    assert K.MAX_OI_STALENESS_MS == 300_000
    oi_source = (
        ROOT / "scripts/research/level_positioning_flow_discovery_v1/oi.py"
    ).read_text()
    assert "funding.jsonl" in oi_source
