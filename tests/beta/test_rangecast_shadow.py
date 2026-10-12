"""Paired shadow forecast side (beta/rangecast_shadow.py, not wired) with the frozen W_L1 artifact.

Synthetic bars only; no network and no market outcome.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "beta"))
from v2_fakes import synthetic_rows  # noqa: E402

from beta import hist_series as hs  # noqa: E402
from beta import rangecast as rc  # noqa: E402
from beta import rangecast_shadow as sh  # noqa: E402
from beta import rangecast_v2 as v2  # noqa: E402

UTC = timezone.utc


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


def _snap(b, *, lag_min: float = 2.0, cal=None, price=None, i=None):
    i = b.last_complete_index() if i is None else i
    sub = b.slice(0, i + 1)
    close = sub.t0 + sub.n * hs.BAR_MS
    now = datetime.fromtimestamp(close / 1000, tz=UTC) + timedelta(minutes=lag_min)
    return sh.Snapshot(bars=sub, price=float(sub.close[-1]) if price is None else price,
                       price_ts=now - timedelta(minutes=1, seconds=30), now=now, calendar=cal or {"events": []})


def _remove(b, idx):
    out = hs.Bars(t0=b.t0, **{c: getattr(b, c).copy() for c in hs.COLUMNS}, oi=b.oi.copy())
    for c in hs.COLUMNS:
        getattr(out, c)[idx] = np.nan
    return out


# ---- the frozen artifact -------------------------------------------------------------------------
def test_the_artifact_is_verified_and_is_w_l1(art):
    assert art["artifact_id"] == sh.MODEL_ARTIFACT_ID and art["spec_id"] == v2.SPEC_ID
    assert art["spec_digest"] == v2.spec_digest() and art["params_digest"] == v2.params_digest(art)
    assert art["level"] == "L1" and art["half_life_days"] == 365.0
    assert art["freeze"]["refused_before_request"] and all("2026-08" in k for k in art["freeze"]["refused_before_request"])


def test_an_altered_artifact_is_refused(tmp_path, art):
    p = tmp_path / "m.json"
    p.write_bytes(sh.MODEL_PATH.read_bytes().replace(b'"L1"', b'"L2"', 1))
    with pytest.raises(sh.ShadowModelError, match="file digest"):
        sh.load_frozen_model(p)
    m = copy.deepcopy(art)
    m["horizons"]["4h"]["beta"][1] += 1e-6
    with pytest.raises(sh.ShadowModelError, match="parameter digest"):
        sh.validate_v2_model(m)
    m = copy.deepcopy(art)
    m["spec_digest"] = "0" * 64
    with pytest.raises(sh.ShadowModelError, match="spec digest"):
        sh.validate_v2_model(m)


def test_pinned_constants_are_the_products():
    from beta import check, claims, decision
    assert sh.TOUCH_GRID_PCT == claims.TOUCH_GRID_PCT and sh.NEITHER_GRID_PCT == claims.NEITHER_GRID_PCT
    assert (sh.MIN_DISTANCE_PCT, sh.MAX_DISTANCE_PCT) == (check.MIN_DISTANCE_PCT, check.MAX_DISTANCE_PCT)
    assert sh.STALE_AFTER == decision.STALE_AFTER and sh.EVENT_ZONE_POST_MS == decision.EVENT_ZONE_POST_MS
    from beta import paired_shadow as ps
    assert (sh.V1_PROCEDURE_ID, sh.V1_SPEC_ID) == (ps.V1_PROCEDURE_ID, ps.V1_SPEC_ID)
    assert (v2.SHADOW_PROCEDURE_ID, v2.SHADOW_SPEC_ID, v2.SHADOW_SYMBOL) == (ps.V2_PROCEDURE_ID, ps.V2_SPEC_ID, ps.PRIMARY_SYMBOL)


# ---- the paired record -----------------------------------------------------------------------------
def test_v1_numbers_are_the_claim_journals(bars, v1):
    """The V1 side reproduces `claims.touch_claims` for the distance grid and «ни один»."""
    from beta import claims
    snap = _snap(bars)
    out = sh.paired_forecast(snap, v1_model=v1, v2_model=None)
    fc = rc.forecast(v1, snap.bars, price=snap.price, events={})
    block = {"available": True, "price": snap.price, "price_ts": snap.price_ts.isoformat(),
             "corridor": {"horizons": fc["horizons"]}, "levels": {}}
    rows = claims.touch_claims(block, v1, now=snap.now, slot=snap.now.replace(minute=0, second=0, microsecond=0))
    by = {(r["claim_class"], r["subject_key"]): r for r in rows}
    n = 0
    for h, x in out["horizons"].items():
        r1 = x["v1"]
        assert r1["as_of"] == by[(f"L3_DISTANCE_TOUCH_{h.upper()}", "+1:0.25")]["as_of"].isoformat()
        for t in r1["touch"]:
            c = by[(f"L3_DISTANCE_TOUCH_{h.upper()}", t["subject_key"])]
            # the journal stores 4 decimals of the raw chance, the adapter 6: equal up to the journal's rounding
            assert abs(t["probability"] - c["numbers"]["probability"]) <= 5.1e-5 and t["level"] == c["subject"]["level"]
            n += 1
        for q in r1["neither"]:
            c = by[(f"L3_NEITHER_{h.upper()}", q["subject_key"])]
            assert abs(q["probability"] - c["numbers"]["probability"]) <= 5.1e-5
            assert (q["level_up"], q["level_down"]) == (c["subject"]["level_up"], c["subject"]["level_down"])
            n += 1
    assert n == 3 * (12 + 16)


def test_v2_numbers_are_the_research_path_at_every_5_minute_anchor(bars, art):
    F = v2.bar_features(bars)
    last = bars.last_complete_index()
    for i in range(last - 11, last + 1):                            # twelve consecutive 5-minute anchors
        out = sh.paired_forecast(_snap(bars, i=i), v1_model=None, v2_model=art)
        for h, x in out["horizons"].items():
            mh = art["horizons"][h]
            st = v2.state(mh, {k: v[[i]] for k, v in F.items()}, v2.calendar_columns(bars, np.array([i]), h, {}))
            for t in x["v2"]["touch"]:
                p = float(v2.touch_prob(mh, st, "up" if t["side"] > 0 else "down", np.array([t["distance_pct"]]))[0])
                assert t["probability"] == round(p, 6)
            for q in x["v2"]["neither"]:
                p = float(v2.neither_prob(mh, st, np.array([q["up_pct"]]), np.array([q["down_pct"]]))[0])
                assert q["probability"] == round(p, 6)


def test_the_two_sides_pair_one_to_one(bars, v1, art):
    from beta import paired_shadow as ps
    out = sh.paired_forecast(_snap(bars), v1_model=v1, v2_model=art, target_prices=[float(bars.close[-1]) * 1.01])
    for h, x in out["horizons"].items():
        assert x["paired"] and x["v1"]["status"] == x["v2"]["status"] == sh.OK
        assert [t["subject_key"] for t in x["v1"]["touch"]] == [t["subject_key"] for t in x["v2"]["touch"]]
        assert [q["subject_key"] for q in x["v1"]["neither"]] == [q["subject_key"] for q in x["v2"]["neither"]]
        assert x["v1"]["as_of"] == x["v2"]["as_of"] and x["v1"]["horizon_end"] == x["v2"]["horizon_end"]
        assert (x["v1"]["procedure_id"], x["v1"]["spec_digest"]) == (ps.V1_PROCEDURE_ID, ps.V1_SPEC_DIGEST)
        assert (x["v2"]["procedure_id"], x["v2"]["spec_digest"]) == (ps.V2_PROCEDURE_ID, ps.V2_SPEC_DIGEST)
        assert x["v1"]["snapshot_id"] == sh.v1_snapshot_id(v1) and x["v2"]["snapshot_id"] == sh.MODEL_PARAMS_DIGEST
    json.dumps(out)


# ---- statuses: never an invented number ----------------------------------------------------------------
def _statuses(out):
    return {h: (x["status"], x["v1"]["status"], x["v2"]["status"]) for h, x in out["horizons"].items()}


def test_stale_data_gives_no_number(bars, v1, art):
    out = sh.paired_forecast(_snap(bars, lag_min=11), v1_model=v1, v2_model=art)
    assert out["status"] == sh.STALE_DATA and all(s == (sh.STALE_DATA,) * 3 for s in _statuses(out).values())
    snap = _snap(bars)
    old = sh.Snapshot(bars=snap.bars, price=snap.price, price_ts=snap.now - timedelta(minutes=12), now=snap.now,
                      calendar=snap.calendar)
    assert sh.paired_forecast(old, v1_model=v1, v2_model=art)["status"] == sh.STALE_DATA
    none = sh.Snapshot(bars=snap.bars, price=None, price_ts=None, now=snap.now, calendar=snap.calendar)
    assert sh.paired_forecast(none, v1_model=v1, v2_model=art)["horizons"]["4h"]["v2"]["touch"] == []


def test_short_history_and_incomplete_windows_give_no_number(bars, v1, art):
    short = bars.slice(bars.n - 5000, bars.n)
    assert sh.paired_forecast(_snap(short), v1_model=v1, v2_model=art)["status"] == sh.INSUFFICIENT_HISTORY
    last = bars.last_complete_index()
    for hole in ([last - 3], list(range(last - 200, last - 197)), list(range(last - 2000, last - 1950))):
        out = sh.paired_forecast(_snap(_remove(bars, hole), i=last), v1_model=v1, v2_model=art)
        assert out["status"] == sh.INCOMPLETE_WINDOW, hole
        assert all(not x["paired"] and x["v2"]["touch"] == [] for x in out["horizons"].values())
    one_old_gap = sh.paired_forecast(_snap(_remove(bars, [last - 5000]), i=last), v1_model=v1, v2_model=art)
    assert one_old_gap["status"] == sh.OK                       # 1 bar in 30 days is inside the 95 % rule


def test_event_zones_withhold_exactly_the_products_horizons(bars, v1, art):
    snap = _snap(bars)
    ahead = {"events": [{"kind": "CPI", "at": snap.now + timedelta(hours=2)}]}
    out = sh.paired_forecast(_snap(bars, cal=ahead), v1_model=v1, v2_model=art)
    assert _statuses(out)["1h"][0] == sh.OK
    assert _statuses(out)["4h"] == (sh.EVENT_ZONE,) * 3 and _statuses(out)["24h"] == (sh.EVENT_ZONE,) * 3
    just_after = {"events": [{"kind": "FOMC", "at": snap.now - timedelta(minutes=30)}]}
    out = sh.paired_forecast(_snap(bars, cal=just_after), v1_model=v1, v2_model=art)
    assert all(s[0] == sh.EVENT_ZONE for s in _statuses(out).values())
    later = {"events": [{"kind": "FOMC", "at": snap.now - timedelta(minutes=61)}]}
    out = sh.paired_forecast(_snap(bars, cal=later), v1_model=v1, v2_model=art)
    assert all(s[0] == sh.OK for s in _statuses(out).values())
    from beta.decision import event_zones
    for cal in (ahead, just_after, later):
        assert set(sh.event_zone_horizons(hs.to_ms(snap.now), cal)) == set(event_zones(hs.to_ms(snap.now), cal))


def test_outside_an_event_zone_the_event_term_is_zero(bars, art):
    """The K0 flag is 1 only for anchors in (r − H, r], all inside the zone: it never moves a shadow number."""
    snap = _snap(bars)
    i = snap.bars.last_complete_index()
    close = hs.to_ms(snap.now) - 2 * 60_000
    events = {"CPI": [close + 25 * 3_600_000], "FOMC": [close - 2 * 3_600_000]}
    for h in ("1h", "4h", "24h"):
        a = v2.state_at(art, snap.bars, i, h, events=events)
        b = v2.state_at(art, snap.bars, i, h, events={})
        assert a == b


def test_a_missing_or_invalid_model_is_a_status(bars, v1, art):
    out = sh.paired_forecast(_snap(bars), v1_model=None, v2_model=art)
    assert all(s == (sh.NOT_COMPUTABLE, sh.NO_MODEL, sh.OK) for s in _statuses(out).values())
    bad = copy.deepcopy(art)
    bad["spec_digest"] = "x"
    out = sh.paired_forecast(_snap(bars), v1_model=v1, v2_model=bad)
    assert all(s == (sh.NOT_COMPUTABLE, sh.OK, sh.MODEL_INVALID) for s in _statuses(out).values())


def test_invalid_targets_carry_a_status_and_no_number(bars, art):
    p = float(bars.close[-1])
    out = sh.paired_forecast(_snap(bars), v1_model=None, v2_model=art,
                             target_prices=[p * 1.0001, p * 1.5, -1, "x", p * 0.99])
    t = [x for x in out["horizons"]["4h"]["v2"]["touch"] if x["source"] == "TARGET"]
    assert [x.get("reason") for x in t[:4]] == ["TOO_CLOSE", "TOO_FAR", "NOT_POSITIVE", "NOT_A_NUMBER"]
    assert all("probability" not in x for x in t[:4])
    assert t[4]["side"] == -1 and t[4]["status"] == sh.OK and 0 < t[4]["probability"] < 1


def test_the_adapter_never_raises(bars, art):
    snap = _snap(bars)
    broken = sh.Snapshot(bars=snap.bars, price=snap.price, price_ts=snap.price_ts, now=snap.now,
                         calendar={"events": [{"kind": "CPI"}]})
    out = sh.paired_forecast(broken, v1_model=None, v2_model=art)
    assert out["status"] == sh.NOT_COMPUTABLE and out["horizons"] == {}


# ---- tails, «ни один», goldens -------------------------------------------------------------------------
def test_tails_the_shadow_keeps_the_scored_research_path(bars, art):
    """as_v1_model drops the 0.001 / 0.005 levels; the chances agree up to 0.99 and the adapter keeps the
    research path above it (a 0.05 % target at 1h can pass 0.99)."""
    snap = _snap(bars)
    i = snap.bars.last_complete_index()
    view = v2.as_v1_model(art)
    for h in ("1h", "4h", "24h"):
        st = v2.state_at(art, snap.bars, i, h, events={})
        for d in (0.05, 0.08, 0.1, 0.25, 1.0, 3.0, 8.0, 20.0):
            p2 = v2.touch_probability_v2(art, h, st, 1, d)
            p1 = rc.touch_probability(view, h, st["S"], d)
            if p2 <= 0.99:
                assert p1 == pytest.approx(p2, abs=1e-12)
            else:
                assert p1 == pytest.approx(0.99) and p2 <= v2.PROB_MAX
    out = sh.paired_forecast(snap, v1_model=None, v2_model=art, target_prices=[snap.price * 1.00051])
    t = out["horizons"]["1h"]["v2"]["touch"][-1]
    st = v2.state_at(art, snap.bars, i, "1h", events={})
    assert t["probability"] == round(v2.touch_probability_v2(art, "1h", st, 1, t["distance_pct"]), 6)


def test_neither_is_monotone_and_inside_the_frechet_bounds(bars, art):
    snap = _snap(bars)
    i = snap.bars.last_complete_index()
    lv = np.exp(np.linspace(np.log(0.05), np.log(20.0), 21))
    for h in ("1h", "4h", "24h"):
        st = {k: np.array([v]) for k, v in v2.state_at(art, snap.bars, i, h, events={}).items()}
        mh = art["horizons"][h]
        N = np.array([[float(v2.neither_prob(mh, st, np.array([a]), np.array([b]))[0]) for b in lv] for a in lv])
        assert (np.diff(N, axis=0) >= -1e-12).all() and (np.diff(N, axis=1) >= -1e-12).all()
        pu = np.array([float(v2.touch_prob(mh, st, "up", np.array([a]))[0]) for a in lv])
        pd_ = np.array([float(v2.touch_prob(mh, st, "down", np.array([b]))[0]) for b in lv])
        assert (N >= np.maximum(1 - pu[:, None] - pd_[None, :], v2.PROB_MIN) - 1e-12).all()
        assert (N <= np.minimum(1 - np.maximum(pu[:, None], pd_[None, :]), v2.PROB_MAX) + 1e-12).all()


GOLDEN = {"1h": (0.486239, 0.184818, 0.932819), "4h": (0.726775, 0.482192, 0.626916),
          "24h": (0.900291, 0.80269, 0.031529)}


def test_golden_outputs_of_the_frozen_artifact(bars, art):
    """A fixed synthetic snapshot: any change of the math or the artifact moves these numbers."""
    out = sh.paired_forecast(_snap(bars), v1_model=None, v2_model=art)
    for h, (p025, p05, n11) in GOLDEN.items():
        x = out["horizons"][h]["v2"]
        got = (x["touch"][0]["probability"], x["touch"][2]["probability"], x["neither"][5]["probability"])
        assert got == pytest.approx((p025, p05, n11), abs=2e-6), (h, got)


# ---- fitting and wiring --------------------------------------------------------------------------------
def test_a_nightly_fit_never_uses_a_window_that_has_not_closed(bars):
    m = v2.fit_range_model_v2(bars, events={})
    assert m["spec_id"] == v2.SPEC_ID and m["spec_digest"] == v2.spec_digest()
    for h, mh in m["horizons"].items():
        assert mh["data_to_ms"] + rc.HORIZON_MS[h] <= bars.end_ms
    cut = bars.slice(0, bars.n - 300)
    m2 = v2.fit_range_model_v2(cut, events={})
    for h, mh in m2["horizons"].items():
        assert mh["data_to_ms"] + rc.HORIZON_MS[h] <= cut.end_ms


def test_the_shadow_is_not_wired_into_the_product():
    """No product module and not the shadow store imports the V2 code (the store pins the identity only)."""
    pat = re.compile(r"^\s*(from\s+\S*\b(rangecast_shadow|rangecast_v2)\s+import|import\s+\S*\b(rangecast_shadow|rangecast_v2)\b|"
                     r"from\s+\S+\s+import\s+[^#\n]*\b(rangecast_shadow|rangecast_v2)\b)", re.M)
    offenders = [str(p.relative_to(ROOT)) for d in ("beta", "runtime", "storage") for p in (ROOT / d).rglob("*.py")
                 if p.name not in ("rangecast_v2.py", "rangecast_shadow.py") and pat.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
