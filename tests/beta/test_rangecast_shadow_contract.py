"""Rangecast V2 against the paired shadow store (beta/paired_shadow.py, docs/BETA_PAIRED_SHADOW_CONTRACT_V1.md).

Integration: the three contract functions, one hourly record through the store's hour path
(`plan_shadow_record`, `execute_hour`) into `ShadowLedger`, the shared outcome, both paired reports, the
separate monitor books, nightly snapshots and the withheld cases. Synthetic bars only; no network, no
database and no market outcome (the store's PostgreSQL dry run is tests/beta/test_paired_shadow_claude_dry_run.py).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "beta"))
from v2_fakes import synthetic_rows  # noqa: E402

from beta import hist_series as hs  # noqa: E402
from beta import paired_shadow as ps  # noqa: E402
from beta import rangecast as rc  # noqa: E402
from beta import rangecast_paired as rp  # noqa: E402
from beta import rangecast_shadow as sh  # noqa: E402
from beta import rangecast_v2 as v2  # noqa: E402
from beta.state_tape import sha256_json  # noqa: E402

UTC = timezone.utc
N_ISSUE_ROWS = 3 * (2 * len(sh.TOUCH_GRID_PCT) + len(sh.NEITHER_GRID_PCT) ** 2) * 2


@pytest.fixture(scope="module")
def bars():
    rows, _ = synthetic_rows(datetime(2026, 5, 1, tzinfo=UTC), 140, seed=9)
    return hs.bars_from_rows(rows)


@pytest.fixture(scope="module")
def v1(bars):
    return rc.fit_range_model(bars, events={}, holdout_days=30)


@pytest.fixture(scope="module")
def art():
    return sh.load_frozen_model()


def _snap(b, i, *, cal=None):
    sub = b.slice(0, i + 1)
    close = sub.t0 + sub.n * hs.BAR_MS
    now = datetime.fromtimestamp(close / 1000, tz=UTC) + timedelta(minutes=2)
    return sh.Snapshot(bars=sub, price=float(sub.close[-1]), price_ts=now - timedelta(minutes=1, seconds=30), now=now,
                       calendar=cal or {"events": []})


def _issue_bar(b, back=320):
    return b.last_complete_index() - back                    # 320 bars (> 24h) of outcome after the issue


# ---- identity ------------------------------------------------------------------------------------------
def test_the_identity_is_the_stores_and_drift_refuses_to_issue(monkeypatch, art):
    """W_L1: the store pins the digest of `spec()`, the model math. V1: the store's digest, behind the V1 math
    guard. A changed constant refuses to issue instead of joining the running book."""
    assert v2.shadow_spec_digest() == ps.V2_SPEC_DIGEST == v2.spec_digest() == art["spec_digest"]
    assert sh.v1_spec_digest() == ps.V1_SPEC_DIGEST and sha256_json(sh.v1_math_spec()) == sh.V1_MATH_DIGEST
    assert (rp.V1_PAIR, rp.V2_PAIR) == ((ps.V1_PROCEDURE_ID, ps.V1_SPEC_ID), (ps.V2_PROCEDURE_ID, ps.V2_SPEC_ID))
    for name, value in (("RIDGE", 2.0), ("Q_GRID", [0.002] + v2.Q_GRID[1:]), ("LOOKBACK_BARS", 8000)):
        with monkeypatch.context() as m:
            m.setattr(v2, name, value)
            with pytest.raises(v2.RangeModelV2Error, match="SPEC_IDENTITY_MISMATCH"):
                v2.shadow_spec_digest()
    for name, value in (("FLOOR_PCT", 0.03), ("PAST_WINDOWS", (12, 48, 288))):
        with monkeypatch.context() as m:
            m.setattr(rc, name, value)
            with pytest.raises(sh.ShadowModelError, match="MATH_MISMATCH"):
                sh.v1_spec_digest()


def test_the_serving_rules_are_pinned():
    """They decide whether a number is issued, never its value, and are outside the digest: a change here is
    registered as a new spec by rule (contract V2 §5), so this test has to change with it."""
    assert v2.MIN_PRESENT == {12: 1.0, 48: 1.0, 288: 0.99, 2016: 0.98, 8640: 0.95}
    assert (v2.SNAPSHOT_MAX_AGE_H, v2.STALE_AFTER_MIN, v2.EVENT_ZONE_POST_MIN) == (72, 10, 60)
    assert (v2.PROB_MIN, v2.PROB_MAX) == (0.001, 0.999)


def test_the_snapshot_id_is_the_coefficients(bars, art):
    assert v2.shadow_snapshot_id(art) == sh.MODEL_PARAMS_DIGEST
    assert v2.shadow_snapshot_id(json.loads(json.dumps(art))) == sh.MODEL_PARAMS_DIGEST
    a = v2.fit_range_model_v2(bars, events={})
    b = v2.fit_range_model_v2(bars.slice(0, bars.n - 288), events={})
    assert v2.shadow_snapshot_id(a) != v2.shadow_snapshot_id(b)              # a refit changes the snapshot …
    assert a["spec_digest"] == b["spec_digest"] == art["spec_digest"]         # … and never the spec


def test_the_bound_model_is_the_stores_class_on_the_research_path(bars, art):
    i = _issue_bar(bars)
    states = {h: v2.state_at(art, bars, i, h, events={}) for h in sh.HORIZONS}
    bound = v2.bind_shadow_model(art, states, snapshot_id=v2.shadow_snapshot_id(art))
    assert isinstance(bound, ps.BoundShadowModel)
    assert (bound.procedure_id, bound.spec_id, bound.spec_digest) == (ps.V2_PROCEDURE_ID, ps.V2_SPEC_ID, ps.V2_SPEC_DIGEST)
    for h in sh.HORIZONS:
        st = {k: np.array([v]) for k, v in states[h].items()}
        for d, side in ((0.37, 1), (1.9, -1)):
            assert bound.touch_probability(horizon=h, distance_pct=d, side=side) == \
                v2.touch_probability_v2(art, h, states[h], side, d)
        assert bound.neither_probability(horizon=h, distance_up_pct=0.8, distance_down_pct=1.7) == \
            float(v2.neither_prob(art["horizons"][h], st, np.array([0.8]), np.array([1.7]))[0])
    only4 = v2.bind_shadow_model(art, {"4h": states["4h"]}, snapshot_id=v2.shadow_snapshot_id(art))
    with pytest.raises(v2.RangeModelV2Error, match="NO_STATE:1h"):
        only4.touch_probability(horizon="1h", distance_pct=1.0, side=1)
    with pytest.raises(v2.RangeModelV2Error, match="SIDE"):
        only4.touch_probability(horizon="4h", distance_pct=1.0, side=0)
    with pytest.raises(v2.RangeModelV2Error, match="SNAPSHOT_ID_MISMATCH"):
        v2.bind_shadow_model(art, states, snapshot_id="0" * 64)
    with pytest.raises(v2.RangeModelV2Error, match="NO_STATE:24h"):
        v2.bind_shadow_model(art, {"24h": None}, snapshot_id=v2.shadow_snapshot_id(art))


# ---- one hourly record through the store's hour path ----------------------------------------------------
def _slot(snap):
    return snap.now.replace(minute=0, second=0, microsecond=0)


def _run_hour(record, ledger, slot, *, bars=None, now=None):
    return ps.execute_hour(record, ledger, issue_slot=slot, allow_write=True, score=bars is not None,
                           bars=bars, now=now)


def test_one_hourly_record_pairs_v1_and_w_l1_on_the_stores_anchors(bars, v1, art):
    i = _issue_bar(bars)
    snap = _snap(bars, i)
    record = sh.paired_forecast(snap, v1_model=v1, v2_model=art)
    planned = ps.plan_shadow_record(record, issue_slot=_slot(snap))
    rows = planned["rows"]
    assert planned["status"] == sh.OK and all(h["status"] == sh.OK for h in planned["horizons"].values())
    assert len(rows) == N_ISSUE_ROWS
    by: dict = {}
    for r in rows:
        by.setdefault(r["anchor_key"], {})[(r["procedure_id"], r["spec_id"])] = r
    assert all(set(p) == {rp.V1_PAIR, rp.V2_PAIR} for p in by.values())
    for r in rows:
        assert r["as_of"] == snap.price_ts + timedelta(minutes=1) and r["issue_slot"] == _slot(snap)
        if r["procedure_id"] == ps.V2_PROCEDURE_ID:
            assert (r["spec_digest"], r["snapshot_id"]) == (ps.V2_SPEC_DIGEST, sh.MODEL_PARAMS_DIGEST)
        else:
            assert (r["spec_digest"], r["snapshot_id"]) == (ps.V1_SPEC_DIGEST, sh.v1_snapshot_id(v1))
    # each model's own path, as the record carries it (6 decimals), on the store's unrounded barrier
    for r in rows:
        if r["family"] != "touch" or r["distance_pct"] != 1.0:
            continue
        h = r["horizon"]
        if r["procedure_id"] == ps.V2_PROCEDURE_ID:
            st = v2.state_at(art, snap.bars, i, h, events={})
            assert r["probability"] == round(v2.touch_probability_v2(art, h, st, r["side"], 1.0), 6)
        else:
            assert r["probability"] == round(rc.touch_probability(v1, h, rc.scale_at(v1, snap.bars, i, h, events={}), 1.0), 6)
        assert r["level_up" if r["side"] > 0 else "level_down"] == snap.price * (1 + r["side"] / 100.0)
    # the hour path: recording off by default, then stored once, scored once, the first probability kept
    ledger = ps.ShadowLedger()
    assert ps.execute_hour(record, ledger, issue_slot=_slot(snap))["written"] is False and not ledger.issues
    end = datetime.fromtimestamp(bars.end_ms / 1000, tz=UTC)
    first = _run_hour(record, ledger, _slot(snap), bars=bars, now=end)
    assert first["written"] and first["inserted"] == len(rows)
    assert {s["status"] for s in first["scoring"]} == {"COMPLETE"}
    assert _run_hour(record, ledger, _slot(snap))["inserted"] == 0
    # the two models stay on separate monitor books, never the production journal's
    assert {(b["procedure_id"], b["spec_id"]) for b in first["books"]} == {rp.V1_PAIR, rp.V2_PAIR}
    assert len(first["books"]) == 2 * 6
    joined = ledger.joined_rows()
    pairs, info = rp.rows_from_ledger(joined)
    assert info["unpaired_anchors"] == 0 and info["identity_faults"] == []
    assert info["v2_snapshot_ids"] == [sh.MODEL_PARAMS_DIGEST] and len(pairs) == len(rows) // 2
    # the store's paired report and this evaluator agree on the pooled log loss and Brier of every book
    theirs = first["paired"]
    assert theirs["n_unscored_anchors"] == 0
    for h in sh.HORIZONS:
        for fam in ("touch", "neither"):
            mine = [x for x in pairs if x["horizon"] == h and x["family"] == fam]
            ll = sum(rp._ll(x["p_v2"], x["outcome"]) - rp._ll(x["p_v1"], x["outcome"]) for x in mine) / len(mine)
            br = sum((x["p_v2"] - x["outcome"]) ** 2 - (x["p_v1"] - x["outcome"]) ** 2 for x in mine) / len(mine)
            cell = theirs["horizons"][h][fam]
            assert cell["n"] == len(mine)
            assert cell["log_loss_v2_minus_v1"] == pytest.approx(ll, abs=1e-12)
            assert cell["brier_v2_minus_v1"] == pytest.approx(br, abs=1e-12)
    assert all("level_up" not in ps.export_row(r) and "level_down" not in ps.export_row(r) for r in joined)


def test_the_production_statistics_row_can_name_the_v1_snapshot(bars, v1, art):
    snap = _snap(bars, _issue_bar(bars))
    record = sh.paired_forecast(snap, v1_model=v1, v2_model=art, v1_ids={"stats_pk": 7, "stats_digest": "b" * 64})
    rows = ps.plan_shadow_record(record, issue_slot=_slot(snap))["rows"]
    assert {r["snapshot_id"] for r in rows if r["procedure_id"] == ps.V1_PROCEDURE_ID} == {"b" * 64}


def test_a_nightly_refit_changes_the_snapshot_not_the_book(bars, v1, art):
    i = _issue_bar(bars, back=340)
    refit = v2.fit_range_model_v2(bars.slice(0, i + 1 - 288), events={})        # the night before the next issue
    s1, s2 = _snap(bars, i), _snap(bars, i + 12)
    ledger = ps.ShadowLedger()
    _run_hour(sh.paired_forecast(s1, v1_model=v1, v2_model=art), ledger, _slot(s1))
    _run_hour(sh.paired_forecast(s2, v1_model=v1, v2_model=refit), ledger, _slot(s2))
    rerun = _run_hour(sh.paired_forecast(s1, v1_model=v1, v2_model=refit), ledger, _slot(s1))
    assert rerun["inserted"] == 0                                                # the first probability is kept
    v2_rows = [r for r in ledger.joined_rows() if r["procedure_id"] == ps.V2_PROCEDURE_ID]
    assert {r["spec_digest"] for r in v2_rows} == {ps.V2_SPEC_DIGEST}
    assert {r["issue_slot"]: r["snapshot_id"] for r in v2_rows} == {_slot(s1): sh.MODEL_PARAMS_DIGEST,
                                                                      _slot(s2): v2.shadow_snapshot_id(refit)}
    _, info = rp.rows_from_ledger(ledger.joined_rows())
    assert info["identity_faults"] == [] and len(info["v2_snapshot_ids"]) == 2


# ---- withheld cases: nothing is stored, the report says why -----------------------------------------------
def test_withheld_horizons_store_a_status_and_no_probability(bars, v1, art, monkeypatch):
    i = _issue_bar(bars)
    snap = _snap(bars, i)

    def hour(record, s=snap):
        ledger = ps.ShadowLedger()
        out = _run_hour(record, ledger, _slot(s))
        return out, ledger

    ahead = {"events": [{"kind": "CPI", "at": snap.now + timedelta(hours=2)}]}
    out, ledger = hour(sh.paired_forecast(_snap(bars, i, cal=ahead), v1_model=v1, v2_model=art))
    assert {r["horizon"] for r in ledger.joined_rows()} == {"1h"}
    assert out["horizons"]["4h"]["status"] == sh.EVENT_ZONE and ledger.hour_status[(_slot(snap), "4h")]["status"] == sh.EVENT_ZONE
    hole = hs.Bars(t0=bars.t0, **{c: getattr(bars, c).copy() for c in hs.COLUMNS}, oi=bars.oi.copy())
    hole.close[i - 3] = np.nan
    out, ledger = hour(sh.paired_forecast(_snap(hole, i), v1_model=v1, v2_model=art))
    assert not ledger.issues and out["horizons"]["4h"]["status"] == sh.INCOMPLETE_WINDOW
    for kw in ({"v1_model": v1, "v2_model": None}, {"v1_model": None, "v2_model": art}):
        out, ledger = hour(sh.paired_forecast(snap, **kw))
        assert not ledger.issues and {h["status"] for h in out["horizons"].values()} == {sh.NOT_COMPUTABLE}
    with monkeypatch.context() as m:
        m.setattr(v2, "RIDGE", 2.0)                              # the code drifted from the registered spec
        record = sh.paired_forecast(snap, v1_model=v1, v2_model=art)
        assert {x["v2"]["status"] for x in record["horizons"].values()} == {sh.MODEL_INVALID}
        out, ledger = hour(record)
        assert not ledger.issues
    with monkeypatch.context() as m:
        m.setattr(rc, "FLOOR_PCT", 0.03)                         # a V1 constant changed under the shadow
        record = sh.paired_forecast(snap, v1_model=v1, v2_model=art)
        assert {x["v1"]["status"] for x in record["horizons"].values()} == {sh.MODEL_INVALID}
    forged = sh.paired_forecast(snap, v1_model=v1, v2_model=art)
    for x in forged["horizons"].values():
        x["v2"]["spec_digest"] = "0" * 64                        # the store refuses an unregistered digest too
    out, ledger = hour(forged)
    assert not ledger.issues and {h["status"] for h in out["horizons"].values()} == {sh.MODEL_INVALID}


# ---- nightly snapshots -------------------------------------------------------------------------------------
def test_nightly_snapshots_are_kept_verified_and_selected(tmp_path, bars, v1):
    cal = {"events": [], "version": "TEST_CAL"}
    end = datetime.fromtimestamp(bars.end_ms / 1000, tz=UTC)
    with pytest.raises(sh.ShadowModelError, match="after the build"):
        sh.fit_nightly_snapshot(bars, calendar=cal, built_at=end - timedelta(minutes=5))
    short = bars.slice(0, bars.n - 288)
    old = sh.fit_nightly_snapshot(short, calendar=cal, built_at=end - timedelta(hours=23))
    new = sh.fit_nightly_snapshot(bars, calendar=cal, built_at=end + timedelta(hours=1))
    assert old["snapshot_id"] != new["snapshot_id"] and old["spec_digest"] == new["spec_digest"] == ps.V2_SPEC_DIGEST
    store = sh.SnapshotStore(tmp_path / "snapshots")
    assert store.select(end)[0] == sh.NO_SNAPSHOT
    assert store.put(old)["stored"] and store.put(new)["stored"]
    assert store.put({**new, "built_at": (end + timedelta(hours=25)).isoformat()})["stored"] is False   # same fit
    assert store.get(new["snapshot_id"]) == json.loads(json.dumps(new))
    status, _, rec = store.select(end)                                   # before the newer build: the older one
    assert status == sh.OK and rec["snapshot_id"] == old["snapshot_id"]
    status, _, rec = store.select(end + timedelta(hours=2))
    assert status == sh.OK and rec["snapshot_id"] == new["snapshot_id"]
    assert store.select(end + timedelta(hours=73))[0] == sh.STALE_SNAPSHOT
    # an issue with the selected snapshot carries its id
    snap = _snap(bars, bars.last_complete_index())
    rows = ps.plan_shadow_record(sh.paired_forecast(snap, v1_model=v1, v2_model=rec["model"]), issue_slot=_slot(snap))["rows"]
    assert {r["snapshot_id"] for r in rows if r["procedure_id"] == ps.V2_PROCEDURE_ID} == {new["snapshot_id"]}
    # a file changed on disk is refused, never used
    path = next(p for p in (tmp_path / "snapshots").iterdir() if new["snapshot_id"] in p.name)
    body = json.loads(path.read_text())
    body["model"]["horizons"]["4h"]["beta"][0] += 1e-9
    path.write_text(json.dumps(body))
    assert store.select(end + timedelta(hours=2))[0] == sh.MODEL_INVALID
    with pytest.raises(sh.ShadowModelError):
        store.get(new["snapshot_id"])
