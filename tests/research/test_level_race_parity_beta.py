"""beta.level_race parity with the research twin (moved out of tests/beta, which must not
import scripts.research)."""

from __future__ import annotations

import numpy as np
import pytest

from beta import level_race as L
from scripts.research.dh1.events import rolling_sigma
from scripts.research.level_race_forecast_v1 import b0 as RB0
from scripts.research.level_race_forecast_v1 import constants as RK
from scripts.research.level_race_forecast_v1 import hist as RH
from scripts.research.level_touch_degradation_v1 import constants as K352


def test_constants_match_research():
    assert L.TAU == RK.TAU and L.BAND_EDGES == RK.BAND_EDGES and L.ZONE_HALF == RK.ZONE_HALF
    assert L.PROB_FLOOR == RK.PROB_FLOOR and L.WINDOW_BARS == K352.HOLD_BARS_PRIMARY
    assert L.barrier_x(0.002) == pytest.approx(K352.x_from_sigma(0.002))
    assert L.FAMILY_OF == K352.FAMILY_OF and L.STRUCT_SIDE == K352.STRUCT_SIDE


@pytest.mark.parametrize("pos,tau", [(100.0, 48), (100.4, 46), (99.1, 46), (103.0, 48), (97.0, 48)])
def test_b0_parity(pos, tau):
    assert L.b0_race(pos, 102.0, 98.0, 0.003, tau) == pytest.approx(RB0.race(pos, 102.0, 98.0, 0.003, tau), abs=1e-12)


def test_sigma_parity_with_352():
    rng = np.random.default_rng(5)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, 700)))
    close[350] = np.nan
    ref = rolling_sigma(close, window=288, min_frac=0.9)
    for j in (289, 400, 600):
        assert L.sigma_before(close, j) == pytest.approx(ref[j - 1], rel=1e-9)


def test_cell_key_parity_with_research():
    row = {"landmark": "T15", "family": "WEEK", "struct_side": -1, "b0_beyond": 0.5}
    assert L.cell_key("T15", "PWL", 0.5) == RH.cell_key(row)
    assert L.cell_key("T0", "PDH") == "T0|DAY|H"
