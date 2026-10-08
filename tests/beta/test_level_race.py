"""beta.level_race (HIST line): parity with the research twin and the frozen table."""

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


def test_table_digest_and_lookup():
    t = L.load_hist_table()
    assert t["table_sha256"] == L.HIST_TABLE_SHA256
    g = L.geometry(99850.0, 100150.0, 0.002, 1)
    line = L.hist_line(t, landmark="T0", kind="PDH", price=100000.0, geo=g, sigma=0.002)
    c = t["cells"]["T0|DAY|H"]
    assert line["template"] == "LR_HIST_V1" and line["n"] == c["n"]
    assert line["h"] == {"up": c["h"]["BEYOND"], "dn": c["h"]["BACK"], "neither": c["h"]["NEITHER"]}
    g2 = L.geometry(99850.0, 100150.0, 0.002, -1)        # approach from above: beyond is the lower price
    line2 = L.hist_line(t, landmark="T0", kind="PDH", price=100000.0, geo=g2, sigma=0.002)
    assert line2["h"]["dn"] == c["h"]["BEYOND"]
    low = L.hist_line(t, landmark="T0", kind="PMH", price=100000.0, geo=g, sigma=0.002)
    assert low["template"] == "LR_HIST_LOW_N_V1" and "h" not in low


def test_cell_key_parity_with_research():
    row = {"landmark": "T15", "family": "WEEK", "struct_side": -1, "b0_beyond": 0.5}
    assert L.cell_key("T15", "PWL", 0.5) == RH.cell_key(row)
    assert L.cell_key("T0", "PDH") == "T0|DAY|H"


def test_t15_eligibility_and_window_end():
    g = {"p_up": 101.0, "p_dn": 99.0}
    high = np.array([100.2] * 10)
    low = np.array([99.8] * 10)
    assert L.t15_eligible(high, low, 3, g)
    high[5] = 101.0
    assert not L.t15_eligible(high, low, 3, g)
    assert L.window_end_ms(0) == 49 * 300_000


def test_percents_sum_to_100():
    assert sum(L.percents({"up": 0.333, "dn": 0.333, "neither": 0.334}).values()) == 100
    assert L.percents({"up": 0.4, "dn": 0.467, "neither": 0.133}) == {"up": 40, "dn": 47, "neither": 13}
