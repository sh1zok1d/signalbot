"""TWAP footprint research code — synthetic fixtures only, no market data."""
import numpy as np
import pandas as pd
import pytest

from scripts.research.twap_footprint import detector as d
from scripts.research.twap_footprint import sealed_run as sr
from scripts.research.twap_footprint.ingest import month_list, refuse_protected


def periodic(n=200, period=10_000, jitter=100, start=1_000_000, seed=1):
    rng = np.random.default_rng(seed)
    return (start + np.arange(n) * period + rng.integers(-jitter, jitter + 1, n)).astype(np.int64)


def test_clean_periodic_chain_is_one_chain_with_end_rule():
    ch = d.build_chains_for_key(periodic(), 250, 1, "Q", 7)
    assert len(ch) == 1 and len(ch[0].slices) == 200
    assert ch[0].period == pytest.approx(10_000, abs=5)
    assert ch[0].end - ch[0].last == pytest.approx(3 * ch[0].period)


def test_one_missed_slice_is_tolerated_two_in_a_row_break_the_chain():
    t = periodic()
    assert [len(c.slices) for c in d.build_chains_for_key(np.delete(t, [50, 120]), 250, 1, "Q", 7)] == [198]
    split = d.build_chains_for_key(np.delete(t, [50, 51]), 250, 1, "Q", 7)
    assert [len(c.slices) for c in split] == [148]       # the 50-slice head is under 15 min


def test_jitter_beyond_tolerance_is_not_a_chain():
    rng = np.random.default_rng(2)
    t = np.sort((1_000_000 + np.arange(200) * 10_000 + rng.integers(-2_000, 2_001, 200)).astype(np.int64))
    assert d.build_chains_for_key(t, 250, 1, "Q", 7) == []


def test_qualification_needs_k_slices_and_duration():
    ch = d.build_chains_for_key(periodic(), 250, 1, "Q", 7)[0]
    q = ch.qualified_at(20, 15 * 60_000)
    assert q - ch.start >= 15 * 60_000 and ch.slices.index(q) >= 19
    assert ch.qualified_at(500, 15 * 60_000) is None


def test_period_bounds():
    assert d.build_chains_for_key(periodic(period=1_000), 250, 1, "Q", 7) == []      # 1 s < 2 s
    assert d.build_chains_for_key(periodic(n=40, period=400_000), 250, 1, "Q", 7) == []


def test_shuffle_keeps_hour_counts_per_key():
    rng = np.random.default_rng(3)
    n = 5000
    p = {"time": np.sort(rng.integers(0, 10 * 3_600_000, n)).astype(np.int64),
         "side": rng.choice([-1, 1], n).astype(np.int8), "q": rng.integers(1, 5, n).astype(np.int64),
         "nkey": rng.integers(1, 5, n).astype(np.int64), "usd": np.full(n, 2000.0)}
    p = d._dedupe_same_ms(p)
    s = d.shuffle_within_hour(p, 7)
    def counts(x):
        return pd.DataFrame({"h": x["time"] // 3_600_000, "s": x["side"], "q": x["q"]}).value_counts().sort_index()
    a, b = counts(p), counts(s)
    assert (a.index == b.index).all() and (abs(a - b) <= 1).all()   # only rare same-ms ties are dropped


def test_injection_is_detected_and_merges_with_real_prints():
    base = {"time": np.array([5_000_000], dtype=np.int64), "side": np.array([1], dtype=np.int8),
            "q": np.array([100_000_000], dtype=np.int64), "nkey": np.array([5_000]), "usd": np.array([50_000.0])}
    inj = d.make_injections(3, 11, 0, 20 * 3_600_000, lambda t: 60_000.0)
    p = d.inject(base, inj)
    chains = d.build_all(p, 500, workers=1)
    rows = d.qualified(chains, 20, 15 * 60_000)
    hit = [d.injection_detected(i, rows) for i in inj]
    long_enough = [((i["stop"] - i["start"]) >= 15 * 60_000 and len(i["times"]) >= 20) for i in inj]
    assert hit == long_enough


def test_merge_and_refractory():
    rows = [{"side": 1, "key_type": "Q", "key": 1, "start": 0, "qualified_at": 100, "last": 900, "end": 1000.0, "period_ms": 10.0, "slices": 30},
            {"side": 1, "key_type": "N", "key": 2, "start": 500, "qualified_at": 80, "last": 1900, "end": 2000.0, "period_ms": 10.0, "slices": 30},
            {"side": -1, "key_type": "Q", "key": 3, "start": 0, "qualified_at": 50, "last": 100, "end": 200.0, "period_ms": 10.0, "slices": 30}]
    eps = d.merge_episodes(rows)
    buy = [e for e in eps if e["side"] == 1][0]
    assert len(eps) == 2 and buy["T"] == 80 and buy["end"] == 2000.0 and buy["key_types"] == "NQ"
    kept, dropped = d.apply_refractory([{"side": 1, "T": 0}, {"side": 1, "T": 3_600_000}, {"side": 1, "T": 6 * 3_600_000}, {"side": -1, "T": 10}])
    assert [e["T"] for e in kept] == [0, 10, 6 * 3_600_000] and dropped[0]["exclusion"] == "REFRACTORY"


def test_bootstrap_pvalues_and_holm():
    rng = np.random.default_rng(4)
    days = np.repeat(np.arange(200), 3)
    null = rng.normal(0, 1, 600)
    b = sr.day_bootstrap(null, days, 2000, 1)
    assert sr.p_two_sided(b, null.mean()) > 0.05
    shifted = null + 1.0
    b2 = sr.day_bootstrap(shifted, days, 2000, 1)
    assert sr.p_one_sided(b2, shifted.mean(), 1.0) < 0.01 and sr.p_two_sided(b2, shifted.mean()) < 0.01
    adj = sr.holm({"a": 0.01, "b": 0.02, "c": 0.5})
    assert adj == {"a": 0.03, "b": 0.04, "c": 0.5}


def test_match_is_nearest_without_replacement():
    pool = {("c",): np.array([0, 10, 20, 30, 40, 50, 60], dtype=np.int64)}
    out = sr.match([25, 26], [("c",), ("c",)], pool)
    assert sorted(out[0]) == [0, 10, 20, 30, 40]
    assert set(out[1]).isdisjoint(out[0]) and len(out[1]) == 2


def test_anchors_sharing_a_time_keep_their_own_controls():
    pool = {("c",): np.arange(0, 200, 10, dtype=np.int64)}
    out = sr.match([100, 100, 50], [("c",), ("c",), None], pool)
    assert len(out[0]) == 5 and len(out[1]) == 5 and set(out[0]).isdisjoint(out[1]) and out[2] == []


def test_anchor_is_strictly_after_the_decision_time():
    assert sr.ceil_min(60_000) == 120_000 and sr.ceil_min(60_001) == 120_000


def test_protected_months_are_refused_and_surfaces_stop_in_2024():
    with pytest.raises(SystemExit):
        refuse_protected("2025-01")
    assert month_list(*sr.SURFACES["DISCOVERY"])[-1] == "2024-12"
    assert month_list(*sr.SURFACES["REPLICATION"])[0] == "2017-08"


def test_scientific_stages_refuse_without_a_frozen_spec(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "SPEC_PATH", tmp_path / "missing.json")
    with pytest.raises(SystemExit):
        sr.h1(tmp_path)


def _synthetic_run(tmp_path, monkeypatch):
    """Three synthetic years of minute data with injected same-side flow and drift after episodes."""
    monkeypatch.setattr(sr, "SURFACES", {"DISCOVERY": ("2028-01", "2030-12"), "REPLICATION": ("2031-01", "2031-12")})
    monkeypatch.setattr(sr, "SPEC_PATH", tmp_path / "spec.json")
    monkeypatch.setattr(sr, "BOOT_B", 500)
    monkeypatch.setattr(sr, "HET_B", 200)
    rng = np.random.default_rng(9)
    run = tmp_path / "run"
    (run / "months").mkdir(parents=True)
    log = []
    for surface, n_eps in (("DISCOVERY", 600), ("REPLICATION", 150)):
        start, end = sr._surface_bounds(surface)
        minutes = np.arange(start // sr.MIN, end // sr.MIN)
        n = len(minutes)
        buy = rng.gamma(2.0, 50_000, n); sell = rng.gamma(2.0, 50_000, n)
        lr = rng.normal(0, 0.0008, n)
        T = np.sort(rng.choice(np.arange(start + 31 * sr.DAY, end - 7 * sr.HOUR, 7 * sr.HOUR), n_eps, replace=False))
        side = rng.choice([-1, 1], n_eps)
        for t, s in zip(T, side):
            i0 = int(sr.ceil_min(t) // sr.MIN - minutes[0])
            (buy if s > 0 else sell)[i0:i0 + 60] += 400_000
            lr[i0:i0 + 60] += s * 0.0003 / 6
        close = 30_000 * np.exp(np.cumsum(lr))
        df = pd.DataFrame({"minute": minutes, "n": 10, "buy_usd": buy, "sell_usd": sell, "close": close})
        ym = pd.to_datetime(df.minute * sr.MIN, unit="ms").dt.strftime("%Y-%m")
        for m, part in df.groupby(ym):
            part.to_parquet(run / "months" / f"minutes_{m}.parquet", index=False)
            log.append({"ym": m, "sha256": "0" * 64})
        pd.DataFrame({"T": T, "side": side, "start": T - 20 * sr.MIN, "end": (T + 40 * sr.MIN).astype(float),
                      "chains": 1, "slices": 30, "period_ms": 10_000.0, "key_types": "Q"}
                     ).to_parquet(run / f"episodes_{surface}.parquet", index=False)
    (run / "ingest_log.jsonl").write_text("\n".join(map(__import__("json").dumps, log)) + "\n")
    (run / "calibration.json").write_text('{"SELECTED": {"TAU_MS": 250, "K": 20, "MIN_DURATION_MIN": 15}}')
    return run


def test_sealed_stages_end_to_end_on_synthetic_data(tmp_path, monkeypatch):
    import json
    run = _synthetic_run(tmp_path, monkeypatch)
    cnt = sr.counts(run)
    assert cnt["STATUS"] == "FEASIBLE" and cnt["GATES"]["REPLICATION_SUPPORT"]
    with pytest.raises(SystemExit):
        sr.h1(run)                                   # nothing runs before the freeze record exists
    rec = sr.freeze(run)
    (run / "freeze_record.json").write_text(json.dumps({"SHA256": rec["SHA256"]}))
    h = sr.h1(run)
    assert h["PASS"] and h["RATIO"] > 1.10
    price = sr.price_cells(run)
    assert set(price["CELLS"]) == {"H2_1h", "H2_6h", "H3"}
    assert price["CELLS"]["H2_1h"]["MEAN_BPS"] > 10 and price["CELLS"]["H2_1h"]["SUPPORTED"]
    assert price["CELLS"]["H2_1h"]["HETEROGENEITY"]["OUTCOME"] in ("PASS", "PASS_MAGNITUDE_VARIES_BY_EPOCH")
    planned = price["CELLS"]["H2_1h"]["HETEROGENEITY"]["ASSESSABILITY_PLANNED"]["STATUS"]
    assert price["CELLS"]["H2_1h"]["HETEROGENEITY_GATE"] == ("NOT_ASSESSABLE" if planned == "NOT_ASSESSABLE"
                                                             else price["CELLS"]["H2_1h"]["HETEROGENEITY"]["OUTCOME"])
    sr.h1(run, "REPLICATION")
    sr.price_cells(run, "REPLICATION", only_cells=[c for c, r in price["CELLS"].items() if r.get("SUPPORTED")])
    assert sr.classify(run)["STATUS"] in ("SUPPORTED_WITH_REPLICATION", "DISCOVERY_SUPPORTED_REPLICATION_FAILED")


def test_replication_outcomes_refused_when_its_support_gate_failed(tmp_path, monkeypatch):
    import json
    run = _synthetic_run(tmp_path, monkeypatch)
    sr.counts(run)
    c = json.loads((run / "counts.json").read_text())
    c["GATES"]["REPLICATION_SUPPORT"] = False
    (run / "counts.json").write_text(json.dumps(c))
    rec = sr.freeze(run)
    (run / "freeze_record.json").write_text(json.dumps({"SHA256": rec["SHA256"]}))
    with pytest.raises(SystemExit):
        sr.h1(run, "REPLICATION")
