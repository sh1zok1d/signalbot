"""Unit B (RANGE_POSITION_4H on Binance 2025-26): scientific identity with Unit A, E1 guard, manifest, missingness.

Synthetic data only; no Vision object is downloaded here."""
import json

import numpy as np
import pytest

from beta.history_data import url_refusal
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import constants as K
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import data as DB
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import evaluate as EB
from scripts.research.rp4h_bitmex_temporal_v1 import constants as KA
from scripts.research.rp4h_bitmex_temporal_v1 import evaluate as EA

E1_START = 1_786_838_400_000   # 2026-08-16T00:00:00Z
E1_END = 1_787_678_400_000     # 2026-08-25T17:20:00Z


def test_shared_scientific_identity_with_unit_a():
    assert EB._bootstrap is EA._bootstrap and EB.assign_route is EA.assign_route and EB._pieces is EA._pieces
    assert (KA.LOOKBACK, KA.HORIZON, KA.BOOT_DRAWS, KA.BOOT_SEED, KA.MIN_VALID_DRAWS) == (48, 12, 2000, 20261117, 1900)
    assert K.PHASE_ORIGIN_MS == KA.PHASE_ORIGIN_MS and K.BAR_MS == KA.BAR_MS


def test_manifest_is_pinned_and_never_touches_the_e1_window():
    objs = DB.manifest()
    keys = [o["key"] for o in objs]
    assert len(keys) == 64 and all(len(o["sha256"]) == 64 for o in objs)
    assert not any("monthly" in k and "2026-08" in k for k in keys)
    for d in range(2, 26):                                                  # dev slice + E1 days: never requested
        assert not any(f"2026-08-{d:02d}" in k for k in keys)
    assert any("2026-08-01" in k for k in keys) and any("2026-08-26" in k for k in keys) and any("2026-10-08" in k for k in keys)
    assert all(url_refusal(K.VISION + k) is None and DB.refusal(K.VISION + k) is None for k in keys)
    body = json.loads((DB.ROOT / K.MANIFEST).read_text())
    assert len(body["REFUSED_BY_E1_GUARD"]) == 10
    assert len(body["EXCLUDED_E1_DEVELOPMENT_SLICE"]["objects_not_requested"]) == 14


def test_fetch_refuses_a_protected_object_before_any_request(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a request was made")
    monkeypatch.setattr(DB.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="REFUSED_PROTECTED_OBJECT"):
        DB.fetch({"key": "data/futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-20.zip", "sha256": "0" * 64})
    with pytest.raises(SystemExit, match="REFUSED_PROTECTED_OBJECT"):
        DB.fetch({"key": "data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip", "sha256": "0" * 64})
    with pytest.raises(SystemExit, match="REFUSED_PROTECTED_OBJECT"):                      # E1-development slice
        DB.fetch({"key": "data/futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-05.zip", "sha256": "0" * 64})


def _rows(t_list):
    return [{"open_ms": int(t), "high": 2.0, "low": 1.0, "close": 1.5} for t in t_list]


def test_series_drops_protected_rows_and_refuses_bad_rows():
    t = [K.SURFACE_START_MS + k * K.BAR_MS for k in range(5)] + [1_785_628_800_000 + K.BAR_MS, E1_START + K.BAR_MS]
    s = DB.series_from_rows(_rows(t))
    assert s["open_ms"].tolist() == t[:5]                                   # rows in the dev slice and E1 are dropped
    with pytest.raises(SystemExit, match="DUPLICATE_OR_UNSORTED_OPEN"):
        DB.series_from_rows(_rows([K.SURFACE_START_MS, K.SURFACE_START_MS]))
    with pytest.raises(SystemExit, match="OFF_GRID_OPEN"):
        DB.series_from_rows(_rows([K.SURFACE_START_MS + 1]))
    with pytest.raises(SystemExit, match="ROW_OUTSIDE_SURFACE"):
        DB.series_from_rows(_rows([K.SURFACE_START_MS - K.BAR_MS]))


def test_holes_census_counts_e1_slots_separately():
    full = np.arange(K.SURFACE_START_MS, K.SURFACE_END_MS, K.BAR_MS, dtype=np.int64)
    keep = ~((full >= 1_785_628_800_000) & (full < 1_786_838_400_000 + 10 * 86_400_000))   # 2026-08-02 .. 25 whole days
    keep[100] = False                                                                     # one other hole
    series = {"open_ms": full[keep], "high": np.ones(keep.sum()), "low": np.ones(keep.sum()), "close": np.ones(keep.sum())}
    c = DB.census(series)
    assert c["holes"] == 24 * 288 + 1
    assert c["holes_in_e1_window"] == (E1_END - E1_START) // K.BAR_MS
    assert c["holes_in_e1_development_slice"] == 14 * 288
    assert c["holes_e1_refused_day_tail"] == 80                               # 2026-08-25 17:20..24:00
    assert c["holes_other"] == 1


def test_anchor_phase_matches_unit_a_clock():
    opens = K.SURFACE_START_MS + np.arange(30, dtype=np.int64) * K.BAR_MS
    m = DB.anchor_mask(opens)
    assert m.sum() == 10 and np.all(((opens[m] + K.BAR_MS) // 60_000) % 15 == 0)


def test_build_sample_is_identical_to_unit_a_on_the_same_bars(monkeypatch):
    rng = np.random.default_rng(9)
    n = 3000
    close = 60000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    t = K.SURFACE_START_MS + np.arange(n, dtype=np.int64) * K.BAR_MS
    drop = np.ones(n, dtype=bool)
    drop[1700] = False
    series = {"open_ms": t[drop], "high": high[drop], "low": low[drop], "close": close[drop],
              "trades": np.ones(int(drop.sum()), dtype=np.int64)}
    end = int(t[-1]) + K.BAR_MS
    monkeypatch.setattr(K, "SURFACE_END_MS", end)
    monkeypatch.setattr(KA, "SURFACE_END_MS", end)
    b = EB.build_sample(series)
    a = EA.build_sample(series)
    for k in ("rp", "ret4", "rv4", "width", "r1", "ret1h", "ret15", "close_ms"):
        assert np.allclose(a[k], b[k], equal_nan=True), k
    i = (b["close_ms"] - K.BAR_MS - K.SURFACE_START_MS) // K.BAR_MS
    assert not np.any((i - 48 <= 1700) & (i >= 1700)) and not np.any(i + 12 == 1700)


def test_run_refuses_until_frozen_and_pinned(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["evaluate", "run"])
    with pytest.raises(SystemExit, match="needs --go"):
        EB.main()
    marker = tmp_path / "r.json"
    marker.write_text("{}")
    monkeypatch.setattr(EB, "RESULT_JSON", marker)
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        EB.run()
    monkeypatch.setattr(K, "CENSUS_PINNED", False)
    with pytest.raises(SystemExit, match="CENSUS_NOT_PINNED"):
        EB.assert_census({"rows": 1, "holes": 0, "holes_sha256": "x"})


def test_surface_constants_are_the_stated_dates():
    import datetime as dt
    ms = lambda *a: int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert K.SURFACE_START_MS == ms(2025, 1, 1) and K.SURFACE_END_MS == ms(2026, 10, 9)
    assert K.PHASE_ORIGIN_MS == ms(2020, 1, 1)
    assert (E1_START, E1_END) == (ms(2026, 8, 16), ms(2026, 8, 25, 17, 20))


def test_outcome_blind_support_equals_the_analysis_sample(monkeypatch):
    rng = np.random.default_rng(11)
    n = 4000
    close = 60000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    t = K.SURFACE_START_MS + np.arange(n, dtype=np.int64) * K.BAR_MS
    keep = np.ones(n, dtype=bool)
    keep[[900, 2500, 2501]] = False
    high[1500:1600] = low[1500:1600] = close[1500:1600] = 61000.0      # flat stretch: zero span windows
    series = {"open_ms": t[keep], "high": high[keep], "low": low[keep], "close": close[keep]}
    monkeypatch.setattr(K, "SURFACE_END_MS", int(t[-1]) + K.BAR_MS)
    sup = EB.support(series)
    sample = EB.build_sample(series)
    assert sup["eligible_anchors"] == sample["rp"].size
    # support never touches the price of the target bar: changing it leaves support unchanged
    s2 = {k: v.copy() for k, v in series.items()}
    s2["close"][-200:] *= 3.0
    assert EB.support(s2)["eligible_anchors"] == sup["eligible_anchors"]
