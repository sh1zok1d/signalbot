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


# ---- model inputs and C1 (F2 PR-4) ------------------------------------------------------------
def _synthetic_bars(days=80, seed=7, vol=0.0025):
    from beta.hist_series import BARS_PER_DAY, Bars
    rng = np.random.default_rng(seed)
    n = days * BARS_PER_DAY
    c = 30000.0 * np.exp(np.cumsum(rng.normal(0, vol, n)))
    o = np.r_[30000.0, c[:-1]]
    wig = np.abs(rng.normal(0, vol / 2, n))
    return Bars(t0=1609459200000, open=o, high=np.maximum(o, c) * (1 + wig), low=np.minimum(o, c) * (1 - wig),
                close=c, volume=np.ones(n), quote=np.ones(n), taker_buy_quote=np.full(n, np.nan),
                oi=np.full(n, np.nan))


def test_model_rows_match_the_research_landmark_rows():
    from beta import level_race_live as LR
    from beta.levels import structural_first_touches
    from scripts.research.level_race_forecast_v1 import events as RE
    b = _synthetic_bars()
    table = L.load_hist_table()
    ref = {(r["j"], r["landmark"]): r for r in RE.landmark_rows(b, RE.first_touches(b, end_ms=b.t0 + b.n * K352.BAR_MS))}
    live = {}
    for ev in LR.events(b):
        for lm in ("T0", "T15"):
            v = LR.landmark_view(b, ev, lm, table)
            if v is not None and ev["j"] + 48 < b.n:
                live[(ev["j"], lm)] = LR.model_row(v)
    short = {e["j"] for e in structural_first_touches(b) if e["ineligible_reason"] == "WINDOW_TOO_SHORT"}
    assert set(live) <= set(ref)                                   # no live row without a research twin
    assert {k for k in ref if k[0] not in short} == set(live)      # the only gap: WINDOW_TOO_SHORT (#383)
    common = set(live)
    assert len(common) > 20
    keys = ("landmark", "family", "struct_side", "side", "position", "p_up", "p_dn", "beyond_is_up", "sigma", "tau",
            "b0_beyond", "b0_back", "b0_neither")
    for k in common:
        for f in keys:
            assert live[k][f] == pytest.approx(ref[k][f], rel=1e-9, abs=1e-12), (k, f)


class _Series:
    def __init__(self, closes):
        self.closes = closes

    def close_at(self, open_ms):
        return self.closes.get(int(open_ms))


def test_c1_input_matches_the_research_ovmm():
    from datetime import datetime, timezone
    from beta import level_race_live as LR
    from scripts.research.level_race_forecast_v1.crossvenue import ovmm_for
    b = _synthetic_bars()
    table = L.load_hist_table()
    rng = np.random.default_rng(11)
    n = 0
    for ev in LR.events(b):
        v = LR.landmark_view(b, ev, "T15", table)
        if v is None:
            continue
        base, dec = LR.c1_instants(v["touch_open_ms"])
        ser, vc = {}, {}
        for name, ven in (("BYBIT_LINEAR_BTCUSDT_PERP", "bybit"), ("OKX_BTC_USDT_SWAP_PERP", "okx")):
            cb, cd = 30000 * (1 + rng.normal(0, 0.002)), 30000 * (1 + rng.normal(0, 0.002))
            ser[name] = _Series({base - K352.BAR_MS: cb, dec - K352.BAR_MS: cd})       # research: 5m bar opens
            vc[ven] = LR.closes_at([{"ts": datetime.fromtimestamp((base - 60_000) / 1000, tz=timezone.utc), "close": cb},
                                    {"ts": datetime.fromtimestamp((dec - 60_000) / 1000, tz=timezone.utc), "close": cd}])
        want = ovmm_for(ser, v["touch_open_ms"], v["side"])
        got = LR.c1_input(b, v, vc)
        assert got["OVMM"] == pytest.approx(want, abs=1e-15)
        n += 1
    assert n > 10


def test_frozen_model_parity_with_the_research_predictor():
    from scripts.research.level_race_forecast_v1.model import TwoHead
    m = L.load_model()
    rng = np.random.default_rng(11)
    kinds = ("PDH", "PDL", "PWH", "PWL", "PMH", "PML")
    for name in ("M1", "G1", "C1"):
        spec = m[name]
        th = TwoHead(spec["spec_r"], spec["spec_b"], spec["beta_r"], spec["beta_b"],
                     tuple(spec["sigma_tercile_edges"]), spec["lambda_per_event"])
        for _ in range(40):
            bb, bk = rng.uniform(0.1, 0.5), rng.uniform(0.1, 0.5)
            b0 = (bb, bk, max(1 - bb - bk, 0.01))
            s = sum(b0)
            b0 = tuple(v / s for v in b0)
            lm = "T15" if rng.uniform() < 0.5 else "T0"
            kind = kinds[rng.integers(6)]
            sigma = float(rng.uniform(0.0008, 0.0025))
            ov = float(rng.normal(0.003, 0.004))
            row = {"landmark": lm, "family": K352.FAMILY_OF[kind], "struct_side": K352.STRUCT_SIDE[kind],
                   "sigma": sigma, "b0_beyond": b0[0], "b0_back": b0[1], "b0_neither": b0[2]}
            extra = None
            if name == "C1":
                mu, sd = spec["c1_moments"]
                extra = {"OVMM": [((ov - mu) / sd) if lm == "T15" else 0.0]}
            ref = th.predict([row], extra)[0]
            got = L.two_head(spec, b0, landmark=lm, kind=None if name == "G1" else kind, sigma=sigma,
                             ovmm=ov if name == "C1" else None)
            assert np.allclose(got, ref, atol=1e-10), (name, got, ref)
