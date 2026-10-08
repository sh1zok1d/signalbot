"""Level race calibrator, monitors and state machine (beta/level_race_calibration.py); synthetic data only."""
import numpy as np
import pytest

from beta import level_race_calibration as L

WEEK = 7 * 86_400_000


def _records(n, rng, *, shift_b=0.0, shift_a=0.0, weeks_per=7.5, sd_b=0.8):
    la = rng.normal(2.0, 0.4, n)
    lb = rng.normal(-0.2, sd_b, n)
    ya = rng.random(n) < L.expit(la + shift_a)
    yb = rng.random(n) < L.expit(lb + shift_b)
    p = L.probs_from_heads(L.expit(la), L.expit(lb))
    out = []
    for i in range(n):
        t = int(i / weeks_per * WEEK)
        out.append({"t_ms": t, "resolved_ms": t + 4 * 3_600_000, "week": int(i / weeks_per),
                    "outcome": "NEITHER" if not ya[i] else ("BREAK" if yb[i] else "REJECT"),
                    "p_raw": p[i].tolist(), "p_pub": p[i].tolist(), "p_b0": p[i].tolist()})
    return out


def test_heads_roundtrip_and_targets():
    p3 = np.array([[0.4, 0.45, 0.15], [0.05, 0.9, 0.05]])
    pa, pc = L.heads_from_probs(p3)
    assert np.allclose(L.probs_from_heads(pa, pc), p3)
    assert L.head_targets("NEITHER") == (0, None)
    assert L.head_targets("BREAK") == (1, 1)
    assert L.head_targets("REJECT") == (1, 0)
    with pytest.raises(ValueError):
        L.head_targets("UNKNOWN")


def test_identity_prior_is_identity_and_worth_n_events():
    rng = np.random.default_rng(1)
    lg = rng.normal(0, 1, 500)
    pr = L.prior_worth([0.0, 1.0], lg, 150)
    hd = {"mean": pr["mean"], "cov": pr["cov"], "center": pr["center"]}
    assert np.allclose(L._map(hd, lg), L.expit(lg))
    # precision = 150 × per-event information
    info = np.linalg.inv(np.array(pr["cov"])) / 150
    x = np.column_stack([np.ones_like(lg), lg - pr["center"]])
    w = L.expit(lg) * (1 - L.expit(lg))
    assert np.allclose(info, (x * w[:, None]).T @ x / lg.size, rtol=1e-4, atol=1e-6)


def test_calibrator_uses_only_outcomes_resolved_before_cutoff():
    rng = np.random.default_rng(2)
    recs = _records(400, rng)
    pri = L.identity_priors(L.raw_logits_by_head(recs) if hasattr(L, "raw_logits_by_head") else
                            {h: L.logit(L.head_arrays(recs, "p_raw")[h][0]) for h in L.HEADS})
    cut = recs[200]["resolved_ms"]
    c1 = L.fit_calibrator("X", recs, pri, cutoff_ms=cut)
    # changing every outcome at or after the cutoff changes nothing
    flipped = [dict(r, outcome="BREAK") if r["resolved_ms"] >= cut else r for r in recs]
    c2 = L.fit_calibrator("X", flipped, pri, cutoff_ms=cut)
    assert c1.version == c2.version
    assert c1.heads["RESOLVE"]["n"] == sum(1 for r in recs if r["resolved_ms"] < cut)
    # a later cutoff is a new version
    assert L.fit_calibrator("X", recs, pri, cutoff_ms=cut + WEEK).version != c1.version


def test_calibrator_moves_toward_a_shift_but_prior_holds_it_back():
    rng = np.random.default_rng(3)
    recs = _records(3000, rng, shift_b=0.8)
    design = {h: L.logit(L.head_arrays(recs, "p_raw")[h][0]) for h in L.HEADS}
    pri = L.identity_priors(design, n_equiv=150)
    few = L.fit_calibrator("X", recs[:100], pri, cutoff_ms=10 ** 15)
    many = L.fit_calibrator("X", recs, pri, cutoff_ms=10 ** 15)
    a_few = few.heads["BREAK_GIVEN_RESOLVE"]["mean"][0]
    a_many = many.heads["BREAK_GIVEN_RESOLVE"]["mean"][0]
    assert 0 < a_few < a_many
    assert abs(a_many - 0.8) < 0.15
    assert L.large_correction(many, design)          # ≈ 18 pp: a drift signal, not a fix
    assert not L.large_correction(few, design) or a_few > 0.4


def test_apply_calibrator_sums_to_one_and_none_is_identity():
    p3 = np.array([[0.3, 0.5, 0.2]])
    assert np.allclose(L.apply_calibrator(None, p3), p3)
    rng = np.random.default_rng(4)
    recs = _records(300, rng, shift_b=0.5)
    design = {h: L.logit(L.head_arrays(recs, "p_raw")[h][0]) for h in L.HEADS}
    cal = L.fit_calibrator("X", recs, L.identity_priors(design), cutoff_ms=10 ** 15)
    out = L.apply_calibrator(cal, p3)
    assert np.isclose(out.sum(), 1.0)
    assert out[0, 0] > 0.3                            # BREAK raised


def test_batch_cutoffs_weekly_then_four_weekly():
    cuts = L.batch_cutoffs(0, 40 * WEEK)
    gaps = np.diff([0] + cuts)
    assert list(gaps[:L.WEEKLY_BATCHES]) == [WEEK] * L.WEEKLY_BATCHES
    assert all(g == 4 * WEEK for g in gaps[L.WEEKLY_BATCHES:])


def test_e_process_is_one_at_start_and_rises_under_drift():
    rng = np.random.default_rng(5)
    assert L.e_value([]) == 1.0
    calm = _records(600, rng)
    drift = _records(600, rng, shift_b=1.0)
    assert L.e_value(calm) < L.E_THRESHOLD
    assert L.e_value(drift) > L.E_THRESHOLD
    # unstarted change points count as 1: the path starts below but near 1
    path = L.e_path(L.e_increments(calm[:3]))
    assert 0.5 < path[0] < 1.5


def test_e_process_null_false_alarm_below_ville_bound():
    rng = np.random.default_rng(6)
    hits = 0
    for _ in range(150):
        n = 500
        pa, pc = L.expit(rng.normal(2, 0.4, n)), L.expit(rng.normal(0, 1, n))
        ya, yb = (rng.random(n) < pa) * 1.0, (rng.random(n) < pc) * 1.0
        hits += L.e_path(L.e_increments_arrays(pa, pc, ya, yb)).max() >= L.E_THRESHOLD
    assert hits / 150 <= 0.1 + 0.05


def test_citl_and_slope():
    rng = np.random.default_rng(7)
    p = L.expit(rng.normal(0, 1, 2000))
    y = (rng.random(2000) < L.expit(L.logit(p) * 1.5)) * 1.0
    wk = np.arange(2000) // 10
    s = L.cal_slope(p, y, wk)
    assert s["lo"] < 1.5 < s["hi"]
    c = L.citl(p, (rng.random(2000) < p) * 1.0, wk)
    assert c["lo"] < 0 < c["hi"]
    assert L.citl([], [], [])["est"] is None


def test_holdout_gate_passes_calibrated_and_fails_shifted():
    rng = np.random.default_rng(8)
    good = L.holdout_gate(_records(650, rng))
    assert good["passed"]
    bad = L.holdout_gate(_records(650, rng, shift_b=0.8))
    assert not bad["passed"]
    assert not L.holdout_gate(_records(100, rng))["passed"]        # fewer than 20 weeks


def _mon(n_live, *, e=1.0, citl_est=0.0, n_epoch=None, ll=(0.01, -0.01, 0.03), large=False, roll=(0.0, -9.0, 9.0)):
    c = {"est": citl_est, "lo": citl_est - 5, "hi": citl_est + 5, "n": n_live, "clusters": 30}
    rc = {"est": roll[0], "lo": roll[1], "hi": roll[2], "n": 100, "clusters": 13}
    sl = {"est": 1.0, "lo": 0.8, "hi": 1.2, "n": n_live, "curve_dev_pp": 2.0}
    lld = {"est": ll[0], "lo": ll[1], "hi": ll[2], "n": 100, "clusters": 13}
    return L.Monitors(n_live=n_live, n_epoch=n_live if n_epoch is None else n_epoch, e_value=e, e_max=e,
                      roll_citl={h: rc for h in L.HEADS}, live_citl={h: c for h in L.HEADS},
                      live_slope={h: sl for h in L.HEADS}, epoch_citl={h: c for h in L.HEADS},
                      roll_ll_vs_b0=lld, epoch_ll_vs_b0=lld, large_correction=large)


def test_state_machine_path():
    st = L.initial_state(holdout_passed=True, model_version="M1@abc", now_ms=0)
    assert st.state == "L3_HISTORY_BACKED"
    assert L.initial_state(holdout_passed=False, model_version="M1", now_ms=0).state == "HIST"
    st = L.next_state(st, health=L.Health(), mon=_mon(100), now_ms=1)
    assert st.state == "L3_HISTORY_BACKED"
    st = L.next_state(st, health=L.Health(), mon=_mon(160), now_ms=2)
    assert st.state == "L3_LIVE"
    # data fault: OFF at once, back to the previous state when healthy
    off = L.next_state(st, health=L.Health(parity_ok=False), mon=None, now_ms=3)
    assert off.state == "OFF" and off.before_off == "L3_LIVE" and "parity_ok" in off.reason
    st = L.next_state(off, health=L.Health(), mon=None, now_ms=4)
    assert st.state == "L3_LIVE"
    # drift
    fb = L.next_state(st, health=L.Health(), mon=_mon(200, e=12.0), now_ms=5)
    assert fb.state == "FALLBACK" and fb.epoch_start == 200 and fb.fallbacks == 1
    # no return before 50 new events, nor while the epoch e-value is not below 1
    assert L.next_state(fb, health=L.Health(), mon=_mon(240, n_epoch=40, e=0.5), now_ms=6).state == "FALLBACK"
    assert L.next_state(fb, health=L.Health(), mon=_mon(260, n_epoch=60, e=1.5), now_ms=6).state == "FALLBACK"
    back = L.next_state(fb, health=L.Health(), mon=_mon(260, n_epoch=60, e=0.5), now_ms=7)
    assert back.state == "L3_LIVE" and back.epoch_start == 260
    # second fallback is final for the version
    fb2 = L.next_state(back, health=L.Health(), mon=_mon(300, large=True), now_ms=8)
    assert fb2.state == "FALLBACK" and fb2.fallbacks == 2
    assert L.next_state(fb2, health=L.Health(), mon=_mon(400, n_epoch=100, e=0.2), now_ms=9).state == "FALLBACK"


def test_state_machine_hist_is_terminal_for_its_version():
    st = L.initial_state(holdout_passed=False, model_version="M1", now_ms=0)
    assert L.next_state(st, health=L.Health(), mon=_mon(500), now_ms=1).state == "HIST"


def test_drift_reasons():
    assert L.drift_reasons(_mon(200)) == []
    assert L.drift_reasons(_mon(200, roll=(20.0, 8.0, 32.0))) == ["rolling_intercept:RESOLVE",
                                                                  "rolling_intercept:BREAK_GIVEN_RESOLVE"]
    assert "worse_than_b0" in L.drift_reasons(_mon(200, ll=(-0.05, -0.08, -0.02)))


def test_challenger_looks_only_at_fixed_counts():
    rng = np.random.default_rng(9)
    recs = _records(600, rng)
    for r in recs:
        r["p_chal"] = r["p_pub"]
    assert L.challenger_look(recs[:149]) is None
    assert L.challenger_look(recs[:200]) is None
    lk = L.challenger_look(recs[:150])
    assert lk is not None and not lk["promoted"]
    assert L.challenger_look(recs[:600])["retired"]


def test_display_contract():
    st = L.initial_state(holdout_passed=True, model_version="M1", now_ms=0)
    d = L.display_contract(st, published_model="B0", calibrator_version="v", holdout_line={"n": 400}, live_line=None)
    assert d["state"] == "L3_HISTORY_BACKED" and d["probabilities"] == "B0" and not d["level_effect_claimed"]
    assert d["accuracy_line"] == "holdout"
    off = L.next_state(st, health=L.Health(data_fresh=False), mon=None, now_ms=1)
    d = L.display_contract(off, published_model="M1", calibrator_version="v", holdout_line={}, live_line={})
    assert d["probabilities"] is None and d["template"] == "lr_off" and d["holdout_line"] is None


def test_input_drift_flags_rate_and_sigma_only_outside_reference():
    rng = np.random.default_rng(10)
    ref = [{"week": w, "sigma": float(rng.normal(1.0, 0.05)), "p_b0": [0.4, 0.45, 0.15]}
           for w in range(80) for _ in range(rng.poisson(7))]
    calm = [dict(r, week=r["week"] + 100) for r in ref if r["week"] < 8]
    assert L.input_drift(ref, calm, ref_weeks=range(80), recent_weeks=range(100, 108)) == []
    hot = [dict(r, sigma=r["sigma"] * 2) for r in calm] * 3
    w = L.input_drift(ref, hot, ref_weeks=range(80), recent_weeks=range(100, 108))
    assert any(x.startswith("median_sigma") for x in w) and any(x.startswith("rate") for x in w)
