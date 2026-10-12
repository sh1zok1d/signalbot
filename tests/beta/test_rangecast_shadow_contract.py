"""Rangecast V2 against the paired shadow store (beta/paired_shadow.py, docs/BETA_PAIRED_SHADOW_CONTRACT_V1.md).

Integration: the three contract functions, one hourly issue through `plan_issues` into `ShadowLedger`, the
shared outcome, both paired reports, the monitor adapter, nightly snapshots and the withheld cases.
Synthetic bars only; no network, no database and no market outcome.
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
def test_the_identity_is_the_stores_and_covers_the_procedure(monkeypatch):
    assert v2.shadow_spec_identity() == ps.V2_SPEC_IDENTITY and sh.v1_spec_identity() == ps.V1_SPEC_IDENTITY
    assert v2.shadow_spec_digest() == ps.V2_SPEC_DIGEST == sha256_json(ps.V2_SPEC_IDENTITY)
    assert sh.v1_spec_digest() == ps.V1_SPEC_DIGEST == sha256_json(ps.V1_SPEC_IDENTITY)
    assert ps.V2_SPEC_IDENTITY["procedure_digest"] == sha256_json(v2.shadow_procedure())
    assert set(v2.shadow_procedure()) == {"math", "fit", "serve"}
    assert (rp.V1_PAIR, rp.V2_PAIR) == ((ps.V1_PROCEDURE_ID, ps.V1_SPEC_ID), (ps.V2_PROCEDURE_ID, ps.V2_SPEC_ID))
    # a change of the math, the fit or the serving rules is a new spec: issuing under the old id is refused
    for name, value in (("RIDGE", 2.0), ("MIN_PRESENT", {**v2.MIN_PRESENT, 12: 0.9}), ("SNAPSHOT_MAX_AGE_H", 96),
                        ("Q_GRID", [0.002] + v2.Q_GRID[1:])):
        with monkeypatch.context() as m:
            m.setattr(v2, name, value)
            with pytest.raises(v2.RangeModelV2Error, match="SPEC_IDENTITY_MISMATCH"):
                v2.shadow_spec_digest()
    with monkeypatch.context() as m:
        m.setattr(rc, "FLOOR_PCT", 0.03)
        with pytest.raises(sh.ShadowModelError, match="SPEC_IDENTITY_MISMATCH"):
            sh.v1_spec_digest()


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


# ---- one hourly issue through the store -------------------------------------------------------------------
def _store_and_score(bars, rows):
    ledger = ps.ShadowLedger()
    with pytest.raises(ps.ShadowRecordingDisabled):
        ledger.record_issues(rows)                                        # off unless the owner allows it
    assert ledger.record_issues(rows, allow_write=True) == {"inserted": len(rows), "kept": 0}
    end = datetime.fromtimestamp(bars.end_ms / 1000, tz=UTC)
    for key, anchor in ledger.anchors.items():
        s = ps.score_anchor(anchor, bars, now=end)
        assert s["status"] == "COMPLETE" and s["coverage"] >= 0.9
        ledger.record_outcome(key, status=s["status"], outcome=s["outcome"], coverage=s["coverage"],
                              eval_rule_digest=anchor["eval_rule_digest"], computed_at=end, allow_write=True)
    return ledger


def test_one_hourly_issue_pairs_v1_and_w_l1_on_the_stores_anchors(bars, v1, art):
    i = _issue_bar(bars)
    snap = _snap(bars, i)
    out = sh.plan_paired_issues(snap, v1_model=v1, v2_model=art)
    rows = out["rows"]
    assert out["report"]["status"] == sh.OK and out["report"]["paired_horizons"] == list(sh.HORIZONS)
    assert len(rows) == N_ISSUE_ROWS
    by: dict = {}
    for r in rows:
        by.setdefault(r["anchor_key"], {})[(r["procedure_id"], r["spec_id"])] = r
    assert all(set(p) == {rp.V1_PAIR, rp.V2_PAIR} for p in by.values())
    for r in rows:
        assert r["as_of"] == snap.price_ts + timedelta(minutes=1) and r["issued_at"] == snap.now
        assert r["issue_slot"] == snap.now.replace(minute=0, second=0, microsecond=0)
        if r["procedure_id"] == ps.V2_PROCEDURE_ID:
            assert (r["spec_digest"], r["snapshot_id"]) == (ps.V2_SPEC_DIGEST, sh.MODEL_PARAMS_DIGEST)
        else:
            assert (r["spec_digest"], r["snapshot_id"]) == (ps.V1_SPEC_DIGEST, sh.v1_snapshot_id(v1))
    # the numbers are each model's own path on the unrounded barrier
    events = {}
    for r in rows:
        if r["family"] != "touch" or r["distance_pct"] != 1.0:
            continue
        h = r["horizon"]
        if r["procedure_id"] == ps.V2_PROCEDURE_ID:
            st = v2.state_at(art, snap.bars, i, h, events=events)
            assert r["probability"] == v2.touch_probability_v2(art, h, st, r["side"], 1.0)
        else:
            assert r["probability"] == rc.touch_probability(v1, h, rc.scale_at(v1, snap.bars, i, h, events=events), 1.0)
    ledger = _store_and_score(bars, rows)
    assert ledger.record_issues(rows, allow_write=True) == {"inserted": 0, "kept": len(rows)}   # a rerun adds nothing
    joined = ledger.joined_rows()
    pairs, info = rp.rows_from_ledger(joined)
    assert info["unpaired_anchors"] == 0 and info["identity_faults"] == []
    assert info["v2_snapshot_ids"] == [sh.MODEL_PARAMS_DIGEST] and len(pairs) == len(rows) // 2
    # the store's paired report and this evaluator agree on the pooled log loss and Brier of every book
    theirs = ps.paired_report(joined)
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
    # monitor V2 keeps W_L1 on its own books, never in the production journal's
    obs = ps.monitor_observations(joined)
    assert {(o["procedure_id"], o["spec_id"]) for o in obs} == {rp.V1_PAIR, rp.V2_PAIR}
    assert all("level_up" not in ps.export_row(r) and "level_down" not in ps.export_row(r) for r in joined)


def test_a_nightly_refit_changes_the_snapshot_not_the_book(bars, v1, art):
    i = _issue_bar(bars, back=340)
    first = sh.plan_paired_issues(_snap(bars, i), v1_model=v1, v2_model=art)["rows"]
    refit = v2.fit_range_model_v2(bars.slice(0, i + 1 - 288), events={})        # the night before the next issue
    later = sh.plan_paired_issues(_snap(bars, i + 12), v1_model=v1, v2_model=refit)["rows"]
    rerun = sh.plan_paired_issues(_snap(bars, i), v1_model=v1, v2_model=refit)["rows"]
    ledger = ps.ShadowLedger()
    ledger.record_issues(first + later, allow_write=True)
    assert ledger.record_issues(rerun, allow_write=True)["inserted"] == 0      # the first probability is kept
    v2_rows = [r for r in ledger.joined_rows() if r["procedure_id"] == ps.V2_PROCEDURE_ID]
    assert {r["spec_digest"] for r in v2_rows} == {ps.V2_SPEC_DIGEST}
    snaps = {r["issue_slot"]: r["snapshot_id"] for r in v2_rows}
    assert sorted(snaps.values()) == sorted([sh.MODEL_PARAMS_DIGEST, v2.shadow_snapshot_id(refit)])
    _, info = rp.rows_from_ledger(ledger.joined_rows())
    assert info["identity_faults"] == [] and len(info["v2_snapshot_ids"]) == 2


# ---- withheld cases: nothing is stored, the report says why -----------------------------------------------
def test_withheld_horizons_store_nothing_for_either_model(bars, v1, art, monkeypatch):
    i = _issue_bar(bars)
    snap = _snap(bars, i)
    ahead = {"events": [{"kind": "CPI", "at": snap.now + timedelta(hours=2)}]}
    out = sh.plan_paired_issues(_snap(bars, i, cal=ahead), v1_model=v1, v2_model=art)
    assert out["report"]["paired_horizons"] == ["1h"] and {r["horizon"] for r in out["rows"]} == {"1h"}
    assert out["report"]["horizons"]["4h"]["status"] == sh.EVENT_ZONE
    hole = hs.Bars(t0=bars.t0, **{c: getattr(bars, c).copy() for c in hs.COLUMNS}, oi=bars.oi.copy())
    hole.close[i - 3] = np.nan
    out = sh.plan_paired_issues(_snap(hole, i), v1_model=v1, v2_model=art)
    assert out["rows"] == [] and out["report"]["status"] == sh.INCOMPLETE_WINDOW
    out = sh.plan_paired_issues(snap, v1_model=v1, v2_model=None)
    assert out["rows"] == [] and {x["v2"] for x in out["report"]["horizons"].values()} == {sh.NO_MODEL}
    out = sh.plan_paired_issues(snap, v1_model=None, v2_model=art)
    assert out["rows"] == [] and {x["v1"] for x in out["report"]["horizons"].values()} == {sh.NO_MODEL}
    with monkeypatch.context() as m:
        m.setattr(v2, "RIDGE", 2.0)                              # the code drifted from the registered spec
        out = sh.plan_paired_issues(snap, v1_model=v1, v2_model=art)
        assert out["rows"] == [] and {x["v2"] for x in out["report"]["horizons"].values()} == {sh.MODEL_INVALID}
    with monkeypatch.context() as m:
        m.setattr(ps, "plan_issues", lambda *a, **k: (_ for _ in ()).throw(ValueError("x")))
        out = sh.plan_paired_issues(snap, v1_model=v1, v2_model=art)
        assert out["rows"] == [] and out["report"]["status"] == sh.NOT_COMPUTABLE


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
    i = bars.last_complete_index()
    out = sh.plan_paired_issues(_snap(bars, i), v1_model=v1, v2_model=rec["model"])
    assert {r["snapshot_id"] for r in out["rows"] if r["procedure_id"] == ps.V2_PROCEDURE_ID} == {new["snapshot_id"]}
    # a file changed on disk is refused, never used
    path = next(p for p in (tmp_path / "snapshots").iterdir() if new["snapshot_id"] in p.name)
    body = json.loads(path.read_text())
    body["model"]["horizons"]["4h"]["beta"][0] += 1e-9
    path.write_text(json.dumps(body))
    assert store.select(end + timedelta(hours=2))[0] == sh.MODEL_INVALID
    with pytest.raises(sh.ShadowModelError):
        store.get(new["snapshot_id"])
