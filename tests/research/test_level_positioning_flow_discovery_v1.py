"""Synthetic and identity tests for LEVEL_POSITIONING_FLOW_DISCOVERY_V1.

No market resolution rate is computed here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from beta.hist_series import Bars
from scripts.research.level_positioning_flow_discovery_v1 import constants as K
from scripts.research.level_positioning_flow_discovery_v1.analyze import y_of
from scripts.research.level_positioning_flow_discovery_v1.cohort import geometry_status
from scripts.research.level_positioning_flow_discovery_v1.features import (
    flow_features,
    oi_features_from_prints,
    oi_prints,
)
from scripts.research.level_positioning_flow_discovery_v1.inference import (
    _fit,
    _z,
    bh_adjust,
    fit_rows,
    freeze_scales,
    redundancy,
    year_dummies,
)
from scripts.research.level_positioning_flow_discovery_v1.oi import FORBIDDEN_NAME, load_bound_oi
from scripts.research.level_touch_degradation_v1.outcomes import classify
from scripts.research.owner_cards_r03 import data as RD

BAR = 300_000
T0 = 1_598_918_400_000


def _prints(values):
    assert len(values) == 13
    return np.asarray(values, dtype=float)


def test_core_identity_and_surface_bound():
    assert RD.btc_dataset_digest() == K.CORE_ZIP_LIST_SHA256
    from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
    bars = load_discovery_bars()
    assert int(bars.times[0]) >= 1_577_836_800_000
    assert int(bars.times[-1]) < K.SURFACE_END_MS
    assert not np.any(bars.times >= K.SURFACE_END_MS)


def test_oi_snapshot_identity_and_no_funding(monkeypatch):
    opened = []
    real_open = Path.open

    def wrapped(self, *args, **kwargs):
        opened.append(self.name)
        if self.name == FORBIDDEN_NAME:
            raise AssertionError("funding opened")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", wrapped)
    series, meta = load_bound_oi()
    assert meta["funding_jsonl_opened"] is False
    assert FORBIDDEN_NAME not in opened
    assert series.sha256 == K.OI_JSONL_SHA256
    assert series.n_rows == K.OI_JSONL_ROWS
    assert series.git_snapshot_id == K.OI_SNAPSHOT_ID
    assert int(series.period_start_ms[0]) == K.OI_FIRST_PERIOD_START_MS
    assert np.all(series.available_at_ms == series.period_start_ms + K.OI_PERIOD_MS)
    assert int(series.period_start_ms[-1]) < K.SURFACE_END_MS
    git = json.loads(Path(
        "docs/research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/SNAPSHOT_5a9d036b.json"
    ).read_text())
    oi_id = next(item for item in git["identity_payload"]["normalized_object_identities"] if item["path"] == "canonical/oi.jsonl")
    assert oi_id["sha256"] == series.sha256
    assert float(series.sum_open_interest[0]) == pytest.approx(39080.231)


def test_oi_change_acceleration_and_fail_closed():
    up = _prints([100 + i for i in range(13)])
    down = _prints([200 - i for i in range(13)])
    assert oi_features_from_prints(up)["OI_CHANGE_60M"] > 0
    assert oi_features_from_prints(down)["OI_CHANGE_60M"] < 0
    accel = np.full(13, 100.0)
    accel[9] = 100.0
    accel[10] = 101.0
    accel[11] = 102.0
    accel[12] = 110.0
    assert oi_features_from_prints(accel)["OI_RECENT_ACCELERATION"] > 0
    decel = np.full(13, 100.0)
    decel[0] = 100.0
    for i in range(1, 10):
        decel[i] = 100.0 + i
    decel[10:] = decel[9]
    assert oi_features_from_prints(decel)["OI_RECENT_ACCELERATION"] < 0
    decision = T0 + 60 * 60_000
    avail = decision - 60 * 60_000 + np.arange(13) * BAR
    values = np.full(13, 100.0)
    assert oi_prints(avail, values, decision) is not None
    gapped = np.delete(avail, 6)
    gapped_values = np.delete(values, 6)
    assert oi_prints(gapped, gapped_values, decision) is None
    future = np.concatenate([avail, [decision + BAR]])
    future_values = np.concatenate([values, [999.0]])
    got = oi_prints(future, future_values, decision)
    assert got is not None and got[-1] == 100.0
    zeros = values.copy()
    zeros[4] = 0.0
    assert oi_prints(avail, zeros, decision) is None
    assert oi_prints(avail, values, K.SURFACE_END_MS) is None


def _bars(n, quote, taker, open_=None, close=None):
    open_ = np.full(n, 100.0) if open_ is None else open_
    close = np.full(n, 100.0) if close is None else close
    return Bars(
        t0=T0,
        open=np.asarray(open_, dtype=float),
        high=np.full(n, 101.0),
        low=np.full(n, 99.0),
        close=np.asarray(close, dtype=float),
        volume=np.full(n, 1.0),
        quote=np.asarray(quote, dtype=float),
        taker_buy_quote=np.asarray(taker, dtype=float),
        oi=np.full(n, np.nan),
    )


def test_oriented_flow_shift_and_touch_bar_excluded():
    n = 16
    quote = np.full(n, 10.0)
    taker = np.full(n, 5.0)
    taker[12] = 10.0
    bars = _bars(n, quote, taker)
    decision = T0 + 12 * BAR
    up = flow_features(bars.open, bars.close, bars.quote, bars.taker_buy_quote, bars.t0, decision, 1)
    assert up["ORIENTED_TAKER_IMBALANCE_60M"] == pytest.approx(0.0)
    buy = np.full(n, 8.0)
    bars = _bars(n, quote, buy)
    got = flow_features(bars.open, bars.close, bars.quote, bars.taker_buy_quote, bars.t0, decision, 1)
    assert got["ORIENTED_TAKER_IMBALANCE_60M"] == pytest.approx(0.6)
    sell = np.full(n, 2.0)
    bars = _bars(n, quote, sell)
    down = flow_features(bars.open, bars.close, bars.quote, bars.taker_buy_quote, bars.t0, decision, -1)
    assert down["ORIENTED_TAKER_IMBALANCE_60M"] == pytest.approx(0.6)
    opposite = flow_features(bars.open, bars.close, bars.quote, bars.taker_buy_quote, bars.t0, decision, 1)
    assert opposite["ORIENTED_TAKER_IMBALANCE_60M"] == pytest.approx(-0.6)
    mixed = np.full(n, 5.0)
    mixed[9:12] = 8.0
    bars = _bars(n, quote, mixed)
    shift = flow_features(bars.open, bars.close, bars.quote, bars.taker_buy_quote, bars.t0, decision, 1)
    assert shift["TAKER_RECENT_SHIFT"] == pytest.approx(0.6)
    quiet = np.zeros(n)
    bars = _bars(n, quiet, quiet)
    failed = flow_features(bars.open, bars.close, bars.quote, bars.taker_buy_quote, bars.t0, decision, 1)
    assert failed["ORIENTED_TAKER_IMBALANCE_60M"] is None
    assert failed["TAKER_RECENT_SHIFT"] is None
    short = _bars(10, np.full(10, 10.0), np.full(10, 5.0))
    assert flow_features(short.open, short.close, short.quote, short.taker_buy_quote, short.t0, decision, 1)["taker_complete_60m"] is False


def test_first_touch_and_barrier_labels():
    base = {
        "touch_number": 1, "open_ms": K.EVENT_START_MS, "window_ok_48": True,
        "side": 1, "x_primary": 0.01, "sigma": 0.002,
    }
    assert geometry_status(base) == "LEGITIMATE"
    assert geometry_status({**base, "touch_number": 2}) == "NOT_FIRST"
    assert geometry_status({**base, "open_ms": K.EVENT_START_MS - BAR}) == "OUTSIDE_WINDOW"
    high = np.array([100, 101, 103, 101, 101], dtype=float)
    low = np.array([100, 100.5, 100.5, 100.5, 100.5], dtype=float)
    assert classify(high, low, 0, 1, 100.0, 101.0, 0.01, 4) == "BREAK"
    high = np.array([100, 100.5, 100.5, 100.5, 100.5], dtype=float)
    low = np.array([100, 100, 98, 100, 100], dtype=float)
    assert classify(high, low, 0, 1, 100.0, 101.0, 0.01, 4) == "REJECT"
    high = np.array([100, 100.2, 100.2, 100.2, 100.2], dtype=float)
    low = np.array([100, 100.0, 100.0, 100.0, 100.0], dtype=float)
    assert classify(high, low, 0, 1, 100.0, 101.0, 0.01, 4) == "NEITHER"
    high = np.array([100, 103, 101, 101, 101], dtype=float)
    low = np.array([100, 98, 100, 100, 100], dtype=float)
    assert classify(high, low, 0, 1, 100.0, 101.0, 0.01, 4) == "AMBIGUOUS"
    assert y_of("BREAK", "RESOLVE_4H") == 1.0
    assert y_of("REJECT", "RESOLVE_4H") == 1.0
    assert y_of("NEITHER", "RESOLVE_4H") == 0.0
    assert y_of("AMBIGUOUS", "RESOLVE_4H") is None
    assert y_of("BREAK", "BREAK_GIVEN_RESOLVED") == 1.0
    assert y_of("REJECT", "BREAK_GIVEN_RESOLVED") == 0.0
    assert y_of("NEITHER", "BREAK_GIVEN_RESOLVED") is None


def _rich(n, slope, rng, *, pseudo=False):
    rows = []
    for i in range(n):
        feature = float(rng.normal())
        year = int(rng.integers(2020, 2025))
        family = ("DAY", "WEEK", "MONTH")[int(rng.integers(0, 3))]
        side = 1 if int(rng.integers(0, 2)) == 0 else -1
        disp = float(rng.normal())
        rel = float(rng.uniform(0.5, 1.5))
        y = slope * feature + 0.4
        rows.append({
            "OI_CHANGE_60M": feature,
            "disp": disp,
            "rel_volume": rel,
            "year": year,
            "family": family,
            "side": side,
            "support": 1.0 if side < 0 else 0.0,
            "vol_tercile": int(rng.integers(0, 3)),
            "time_block": int(rng.integers(0, 4)),
            "cluster": i // 4,
            "y": y,
            "real": 0.0 if pseudo else 1.0,
            "epoch": "2020Q4" if year == 2020 else str(year),
            "week": i // 4,
            "nuisance_ok": True,
        })
    return rows


def test_scale_fdr_support_loyo_and_specificity():
    assert _z(2.0, {"mean": 0.0, "sd": 2.0}) == pytest.approx(1.0)
    z = np.linspace(-1.0, 1.0, 40)
    x = np.column_stack([np.ones(z.size), z])
    beta = _fit(x, 0.25 * z)
    assert beta[1] == pytest.approx(0.25)
    adjusted = bh_adjust([0.01, 0.2, 0.03, 0.04])
    assert adjusted[0] == pytest.approx(0.04)
    assert adjusted[1] == pytest.approx(0.2)
    rng = np.random.default_rng(0)
    rows = _rich(120, 0.05, rng)
    rows.append({**rows[0], "OI_CHANGE_60M": None, "y": 1.0, "cluster": 999})
    rows.append({**rows[1], "y": None, "cluster": 1000})
    scales = freeze_scales(rows, ["OI_CHANGE_60M"])
    cell = fit_rows(rows, "OI_CHANGE_60M", scales, draws=0)
    assert cell["n"] == 120
    kept = [row for row in rows if row["year"] != 2022]
    assert "y2022" not in year_dummies(kept)
    assert year_dummies(kept)[0] == "y2021"
    real = _rich(90, 0.2, rng, pseudo=False)
    pseudo = _rich(90, 0.0, rng, pseudo=True)
    stacked = []
    for i, (left, right) in enumerate(zip(real, pseudo)):
        stacked.append({**left, "real": 1.0, "cluster": i // 3})
        stacked.append({**right, "real": 0.0, "cluster": i // 3})
    scales = freeze_scales(real, ["OI_CHANGE_60M"])
    spec = fit_rows(stacked, "OI_CHANGE_60M", scales, stacked=True, draws=0)
    assert spec["delta"] is not None and spec["delta"] > 0.05
    assert spec["beta_real"] > spec["beta_pseudo"]
    twin = [dict(row) for row in real]
    for row in twin:
        row["OI_RECENT_ACCELERATION"] = row["OI_CHANGE_60M"]
    dropped = redundancy(twin, ("OI_CHANGE_60M", "OI_RECENT_ACCELERATION"))
    assert dropped["kept"] == ["OI_CHANGE_60M"]
    assert dropped["dropped"][0]["reason"] == "redundancy"
