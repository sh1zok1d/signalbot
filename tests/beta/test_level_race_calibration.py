"""Level race calibrator, gates, monitors and state machine (beta/level_race_calibration.py); synthetic only."""
import numpy as np
import pytest

from beta import level_race_calibration as L

WEEK = 7 * 86_400_000
ACC = {src: {"predicted": 0.4, "realized": 0.38, "n": 420} for src in ("holdout", "live", "generic")}
H4 = 4 * 3_600_000


def _recs(n, rng, *, cls="LEVEL_T0", shift_b=0.0, shift_r=0.0, per_week=7.5, sd_b=0.8, t0=0, slope_b=1.0):
    lr, lb = rng.normal(1.1, 0.5, n), rng.normal(-0.2, sd_b, n)
    ya = rng.random(n) < L.expit(lr + shift_r)
    yb = rng.random(n) < L.expit(-0.2 + slope_b * (lb + 0.2) + shift_b)
    p = L.probs_from_heads(L.expit(lr), L.expit(lb))
    out = []
    for i in range(n):
        t = t0 + int(i / per_week * WEEK)
        out.append({"cal_class": cls, "t_ms": t, "resolved_ms": t + H4, "week": t // WEEK,
                    "outcome": "NEITHER" if not ya[i] else ("BREAK" if yb[i] else "REJECT"), "weight": 1.0,
                    "p_raw": p[i].tolist(), "p_pub": p[i].tolist(), "p_b0": p[i].tolist(), "p_fb": p[i].tolist()})
    return out


def test_heads_roundtrip_and_targets():
    p3 = np.array([[0.4, 0.45, 0.15], [0.05, 0.9, 0.05]])
    assert np.allclose(L.probs_from_heads(*L.heads_from_probs(p3)), p3)
    assert L.head_targets("NEITHER") == (0, None)
    assert L.head_targets("BREAK") == (1, 1)
    with pytest.raises(ValueError):
        L.head_targets("UNKNOWN")


def test_identity_prior_structure():
    pr = L.identity_prior(1.0)
    cov = np.array(pr["cov"])
    assert pr["mean"] == [0.0, 0.0, 0.0, 1.0, 1.0]
    d = np.array([[-1, 1, 0, 0, 0], [-1, 0, 1, 0, 0]], dtype=float)     # a_level − a_G
    assert np.allclose(d @ cov @ d.T, np.eye(2) * 1.0)
    assert np.isclose(cov[0, 0], 0.25) and np.isclose(cov[3, 3], 0.0625)
    assert np.allclose(d @ cov[:, 0], 0.0)


def test_calibrator_uses_only_outcomes_resolved_before_cutoff():
    rng = np.random.default_rng(2)
    recs = _recs(400, rng)
    pri = {h: L.identity_prior() for h in L.HEADS}
    cut = recs[200]["resolved_ms"]
    c1 = L.fit_calibrator(recs, pri, cutoff_ms=cut)
    flipped = [dict(r, outcome="BREAK") if r["resolved_ms"] >= cut else r for r in recs]
    assert L.fit_calibrator(flipped, pri, cutoff_ms=cut).version == c1.version
    assert c1.heads["R"]["n"]["LEVEL_T0"] == sum(1 for r in recs if r["resolved_ms"] < cut)
    assert L.fit_calibrator(recs, pri, cutoff_ms=cut + WEEK).version != c1.version


def test_class_intercepts_and_generic_fallback_intercept():
    rng = np.random.default_rng(3)
    gen = _recs(3000, rng, cls="GENERIC", per_week=40)
    lvl = _recs(800, rng, cls="LEVEL_T0", shift_r=0.9)
    cal = L.fit_calibrator(gen + lvl, {h: L.identity_prior(1.0) for h in L.HEADS}, cutoff_ms=10 ** 15)
    th = cal.heads["R"]["mean"]
    assert abs(th[0]) < 0.2 and th[1] - th[0] > 0.6
    p = np.array([0.3, 0.3, 0.4])
    assert L.apply_calibrator(cal, p, "LEVEL_T0")[2] < L.apply_calibrator(cal, p, "GENERIC")[2]
    assert np.isclose(L.apply_calibrator(cal, p, "GENERIC").sum(), 1.0)


def test_small_s_level_pulls_level_toward_generic():
    rng = np.random.default_rng(4)
    gen = _recs(3000, rng, cls="GENERIC", per_week=40)
    lvl = _recs(60, rng, cls="LEVEL_T0", shift_r=0.9)
    a = {}
    for s in (0.5, 1.5):
        cal = L.fit_calibrator(gen + lvl, {h: L.identity_prior(s) for h in L.HEADS}, cutoff_ms=10 ** 15)
        a[s] = cal.heads["R"]["mean"][1] - cal.heads["R"]["mean"][0]
    assert a[0.5] < a[1.5]


def test_slope_moves_toward_truth_with_holdout_size():
    rng = np.random.default_rng(5)
    recs = _recs(520, rng, sd_b=1.0, slope_b=0.78)
    cal = L.fit_calibrator(recs, {h: L.identity_prior() for h in L.HEADS}, cutoff_ms=10 ** 15)
    assert cal.heads["B"]["mean"][4] < 0.95


def test_live_prior_keeps_mean_and_is_wider_than_the_holdout_posterior():
    rng = np.random.default_rng(6)
    recs = _recs(600, rng, shift_b=0.4)
    cal = L.fit_calibrator(recs, {h: L.identity_prior() for h in L.HEADS}, cutoff_ms=10 ** 15)
    lp = L.live_prior(cal, recs, n_equiv=150)
    assert np.allclose(lp["B"]["mean"], cal.heads["B"]["mean"])
    assert np.array(lp["B"]["cov"])[1, 1] > np.array(cal.heads["B"]["cov"])[1, 1]


def test_batch_cutoffs_weekly_then_four_weekly():
    gaps = np.diff([0] + L.batch_cutoffs(0, 40 * WEEK))
    assert list(gaps[:L.WEEKLY_BATCHES]) == [WEEK] * L.WEEKLY_BATCHES
    assert all(g == 4 * WEEK for g in gaps[L.WEEKLY_BATCHES:])


def test_d1_null_false_alarm_and_power():
    rng = np.random.default_rng(7)
    fa = 0
    for _ in range(100):
        mx = L.d1_paths(_recs(500, rng), "p_pub").max(axis=0)
        fa += L.d1_triggered({"e": dict(zip(L.OUTCOMES, mx))})
    assert fa / 100 <= 0.1
    assert L.d1_triggered(L.d1_value(_recs(600, rng, shift_r=-1.0), "p_pub"))


def test_gates_pass_calibrated_and_fail_shifted():
    rng = np.random.default_rng(8)
    good = L.gates(_recs(650, rng))
    assert good["G0"]["pass"] and good["G2"]["pass"] and good["G3"]["pass"]
    bad = L.gates(_recs(650, rng, shift_r=-0.8))
    assert not bad["G2"]["pass"] and not bad["passed"]
    assert not L.gates(_recs(150, rng))["G0"]["pass"]


def _mon(n_live, *, d1=1.0, d2=(0.0, -9.0, 9.0), n_epoch=None, live_ok=True, fb_recent=None, d3=None):
    c = {"est": d2[0], "lo": d2[1], "hi": d2[2], "n": 100, "clusters": 13}
    return L.Monitors(key="p_pub", n_live=n_live, n_epoch=n_live if n_epoch is None else n_epoch,
                      d1={"e": {o: d1 for o in L.OUTCOMES}, "e_max": {o: d1 for o in L.OUTCOMES}},
                      d2={o: c for o in L.OUTCOMES}, d3=d3,
                      epoch_citl={o: {"est": d2[0], "lo": None, "hi": None, "n": 60} for o in L.OUTCOMES},
                      live_gates={"G2": live_ok, "G3": live_ok}, fallback_g2_recent=fb_recent)


def test_mode_hist_only_is_hist_or_off():
    s = L.Setup(mode="HIST_ONLY", case="A", holdout_passed=True, fallback_g2_holdout=True)
    st = L.initial_state(s, now_ms=0)
    assert st.state == "HIST"
    assert L.next_state(st, s, health=L.Health(), mon=_mon(500, d1=50.0), now_ms=1).state == "HIST"
    off = L.next_state(st, s, health=L.Health(data_fresh=False), now_ms=2)
    assert off.state == "OFF" and off.off_reason.startswith("D0")
    assert L.next_state(off, s, health=L.Health(), now_ms=3).state == "HIST"
    on = L.next_state(st, L.Setup(mode="MODEL", case="A", holdout_passed=True), health=L.Health(), now_ms=4)
    assert on.state == "L3_HISTORY_BACKED"


def test_state_machine_case_a_with_fallback():
    s = L.Setup(mode="MODEL", case="A", holdout_passed=True, fallback_g2_holdout=True, model_version="M")
    st = L.initial_state(s, now_ms=0)
    assert st.state == "L3_HISTORY_BACKED"
    st = L.next_state(st, s, health=L.Health(), mon=_mon(160), now_ms=1)
    assert st.state == "L3_LIVE"
    fb = L.next_state(st, s, health=L.Health(), mon=_mon(200, d1=40.0), mon_fb=_mon(200, fb_recent=True), now_ms=2)
    assert fb.state == "FALLBACK" and fb.epoch_start == 200 and fb.drift_exits == 1
    h = L.next_state(fb, s, health=L.Health(), mon=_mon(300), mon_fb=_mon(300, fb_recent=False), now_ms=3)
    assert h.state == "HIST" and h.reason.startswith("fallback_drift")
    assert L.next_state(fb, s, health=L.Health(), mon=_mon(240, n_epoch=40, d1=0.5),
                        mon_fb=_mon(240, fb_recent=True), now_ms=4).state == "FALLBACK"
    assert L.next_state(fb, s, health=L.Health(), mon=_mon(260, n_epoch=60, d1=1.5),
                        mon_fb=_mon(260, fb_recent=True), now_ms=4).state == "FALLBACK"
    back = L.next_state(fb, s, health=L.Health(), mon=_mon(260, n_epoch=60, d1=0.5),
                        mon_fb=_mon(260, fb_recent=True), now_ms=5)
    assert back.state == "L3_LIVE" and back.epoch_start == 260


def test_state_machine_no_fallback_goes_to_hist_and_second_exit_is_final():
    s = L.Setup(mode="MODEL", case="A", holdout_passed=True, fallback_g2_holdout=False)
    st = L.initial_state(s, now_ms=0)
    h = L.next_state(st, s, health=L.Health(), mon=_mon(120, d2=(14.0, 3.0, 25.0)), now_ms=1)
    assert h.state == "HIST" and h.reason.startswith("drift:D2")
    back = L.next_state(h, s, health=L.Health(), mon=_mon(180, n_epoch=60, d1=0.4), now_ms=2)
    assert back.state == "L3_LIVE"
    h2 = L.next_state(back, s, health=L.Health(), mon=_mon(200, d1=40.0), now_ms=3)
    assert h2.state == "HIST" and h2.drift_exits == 2
    assert L.next_state(h2, s, health=L.Health(), mon=_mon(400, n_epoch=200, d1=0.1), now_ms=4).state == "HIST"


def test_case_b_never_enters_l3():
    s = L.Setup(mode="MODEL", case="B", holdout_passed=True, fallback_g2_holdout=True)
    st = L.initial_state(s, now_ms=0)
    assert st.state == "FALLBACK"
    for k in range(1, 6):
        st = L.next_state(st, s, health=L.Health(), mon=_mon(100 * k + 160, n_epoch=200, d1=0.2), now_ms=k)
        assert not st.state.startswith("L3")
    h = L.next_state(st, s, health=L.Health(), mon=_mon(900, d1=40.0), now_ms=9)
    assert h.state == "HIST" and h.drift_exits == 1
    back = L.next_state(h, s, health=L.Health(), mon=_mon(960, n_epoch=60, d1=0.4), now_ms=10)
    assert back.state == "FALLBACK"
    assert L.display_contract(back, s, calibrator_version="v", accuracy=ACC)["probabilities"] == "FALLBACK"
    assert L.initial_state(L.Setup(mode="MODEL", case="B", holdout_passed=True, fallback_g2_holdout=False),
                           now_ms=0).state == "HIST"


def test_calibrator_at_selects_latest_cutoff_not_after_t():
    pri = {h: L.identity_prior() for h in L.HEADS}
    rng = np.random.default_rng(14)
    recs = _recs(300, rng)
    vs = [L.fit_calibrator(recs, pri, cutoff_ms=c) for c in (WEEK, 2 * WEEK, 3 * WEEK)]
    p0 = L.prior_calibrator(pri)
    assert L.calibrator_at(2 * WEEK, vs, p0).version == vs[1].version
    assert L.calibrator_at(2 * WEEK - 1, vs, p0).version == vs[0].version
    assert L.calibrator_at(WEEK - 1, vs, p0) is p0
    assert L.calibrator_at(10 * WEEK, list(reversed(vs)), p0).version == vs[2].version


def test_failed_holdout_is_terminal_and_offers_fallback_only_if_it_passes_g2():
    assert L.initial_state(L.Setup(mode="MODEL", case="A", holdout_passed=False, fallback_g2_holdout=False),
                           now_ms=0).state == "HIST"
    s = L.Setup(mode="MODEL", case="A", holdout_passed=False, fallback_g2_holdout=True)
    st = L.initial_state(s, now_ms=0)
    assert st.state == "FALLBACK"
    assert L.next_state(st, s, health=L.Health(), mon=_mon(300, n_epoch=300, d1=0.2),
                        mon_fb=_mon(300, fb_recent=True), now_ms=1).state == "FALLBACK"


def test_d3_triggers_only_when_published_is_worse_than_fallback():
    d3 = {"est": 0.05, "lo": 0.01, "hi": 0.09, "n": 100, "clusters": 13}
    assert "D3" in L.drift_reasons(_mon(200, d3=d3))
    assert "D3" not in L.drift_reasons(_mon(200, d3={**d3, "lo": -0.01}))


def test_monitors_on_records():
    rng = np.random.default_rng(9)
    recs = _recs(300, rng)
    m = L.monitors(recs, key="p_pub", epoch_start=100, fallback_key="p_fb")
    assert m.n_live == 300 and m.n_epoch == 200
    assert m.d3["est"] == 0 and "D3" not in L.drift_reasons(m)   # identical probabilities: no gap
    assert m.fallback_g2_recent in (True, False)


def test_split_by_events():
    parts = L.split_by_events([{"t_ms": t} for t in (1, 5, 10, 20)], [10])
    assert [len(p[2]) for p in parts] == [2, 2]


def test_challenger_looks_only_at_fixed_counts():
    rng = np.random.default_rng(10)
    recs = _recs(600, rng)
    for r in recs:
        r["p_chal"] = r["p_pub"]
    assert L.challenger_look(recs[:149]) is None
    assert L.challenger_look(recs[:200]) is None
    assert not L.challenger_look(recs[:150])["promoted"]
    assert L.challenger_look(recs[:600])["retired"]


def test_input_drift():
    rng = np.random.default_rng(11)
    ref = [{"week": w, "sigma": float(rng.normal(1.0, 0.05)), "p_b0": [0.4, 0.45, 0.15]}
           for w in range(80) for _ in range(rng.poisson(7))]
    calm = [dict(r, week=r["week"] + 100) for r in ref if r["week"] < 8]
    assert not [w for w in L.input_drift(ref, calm, ref_weeks=range(80), recent_weeks=range(100, 108))
                if not w.startswith("rate")]
    hot = [dict(r, sigma=r["sigma"] * 2) for r in calm] * 3
    assert len(L.input_drift(ref, hot, ref_weeks=range(80), recent_weeks=range(100, 108))) >= 2


def test_display_contract():
    s = L.Setup(mode="MODEL", case="A", holdout_passed=True)
    d = L.display_contract(L.initial_state(s, now_ms=0), s, calibrator_version="v", accuracy=ACC)
    assert d["state"] == "L3_HISTORY_BACKED" and d["probabilities"] == "CHAMPION" and d["template"] == "LR_L3H_V1"
    off = L.next_state(L.initial_state(s, now_ms=0), s, health=L.Health(parity_ok=False), now_ms=1)
    d = L.display_contract(off, s, calibrator_version="v")
    assert d["probabilities"] is None and d["template"] == "LR_OFF_V1" and d["calibrator_version"] is None


def test_d1_margin_variant_tolerates_small_offsets_but_not_large():
    rng = np.random.default_rng(12)
    small = _recs(800, rng, shift_r=-0.15)                 # ≈ 3 pp miscalibration
    m = {o: 0.04 for o in L.OUTCOMES}
    assert L.d1_paths(small, "p_pub", margin=m)[-1].max() < L.d1_paths(small, "p_pub")[-1].max()
    big = _recs(800, rng, shift_r=-1.0)
    assert L.d1_triggered({"e": dict(zip(L.OUTCOMES, L.d1_paths(big, "p_pub", margin=m)[-1]))})


def test_shared_slope_ties_and_hierarchical_slope_frees_the_level_slope():
    rng = np.random.default_rng(13)
    gen = _recs(4000, rng, cls="GENERIC", per_week=40, sd_b=1.0)
    lvl = _recs(500, rng, cls="LEVEL_T0", sd_b=1.0, slope_b=0.7)
    shared = L.fit_calibrator(gen + lvl, {h: L.identity_prior(1.0, 0.0) for h in L.HEADS}, cutoff_ms=10 ** 15)
    hier = L.fit_calibrator(gen + lvl, {h: L.identity_prior(1.0, 0.25) for h in L.HEADS}, cutoff_ms=10 ** 15)
    bs, bh = shared.heads["B"]["mean"], hier.heads["B"]["mean"]
    assert abs(bs[3] - bs[4]) < 1e-3                   # tied
    assert bh[4] < bh[3] - 0.1                         # the level slope moves toward 0.7
    pr = np.array(L.identity_prior(1.0, 0.25)["cov"])
    assert np.isclose(pr[4, 4] - 2 * pr[3, 4] + pr[3, 3], 0.0625)


def test_prior_for_cases_uses_case_s_level():
    pr = L.prior_for_cases("A", "B")
    cov = np.array(pr["R"]["cov"])
    d0, d15 = np.array([-1, 1, 0, 0, 0.0]), np.array([-1, 0, 1, 0, 0.0])
    assert np.isclose(d0 @ cov @ d0, L.PRIOR_S_LEVEL_BY_CASE["A"] ** 2)
    assert np.isclose(d15 @ cov @ d15, L.PRIOR_S_LEVEL_BY_CASE["B"] ** 2)


def test_fallback_prints_no_separate_usual_and_claims_no_level_offset():
    for case in ("A", "B"):
        s = L.Setup(mode="MODEL", case=case, holdout_passed=False, fallback_g2_holdout=True)
        st = L.initial_state(s, now_ms=0)
        assert st.state == "FALLBACK"
        d = L.display_contract(st, s, calibrator_version="v", accuracy=ACC)
        assert d["probabilities"] == "FALLBACK" and d["usual"] is None and d["level_effect_claimed"] is False
        assert d["template"] == "LR_FB_V1" and d["accuracy_line"]["source"] == "generic"
    s = L.Setup(mode="MODEL", case="A", holdout_passed=True)
    d = L.display_contract(L.initial_state(s, now_ms=0), s, calibrator_version="v", accuracy=ACC)
    assert d["usual"] == "G1_AT_EVENT_RAW"


def test_no_model_number_without_its_accuracy_line():
    cases = [(L.Setup(mode="MODEL", case="A", holdout_passed=True), "holdout"),
             (L.Setup(mode="MODEL", case="B", fallback_g2_holdout=True), "generic")]
    for s, src in cases:
        st = L.initial_state(s, now_ms=0)
        with pytest.raises(ValueError):
            L.display_contract(st, s, calibrator_version="v")
        with pytest.raises(ValueError):
            L.display_contract(st, s, calibrator_version="v", accuracy={src: {"predicted": 0.4, "n": 10}})
        d = L.display_contract(st, s, calibrator_version="v", accuracy=ACC)
        assert d["accuracy_line"]["source"] == src and d["accuracy_line"]["n"] == 420
    live = L.next_state(L.initial_state(cases[0][0], now_ms=0), cases[0][0], health=L.Health(), mon=_mon(160), now_ms=1)
    assert live.state == "L3_LIVE"
    with pytest.raises(ValueError):
        L.display_contract(live, cases[0][0], calibrator_version="v", accuracy={"holdout": ACC["holdout"]})
    # states without a number need no line
    h = L.initial_state(L.Setup(mode="HIST_ONLY"), now_ms=0)
    assert L.display_contract(h, L.Setup(mode="HIST_ONLY"), calibrator_version=None)["accuracy_line"] is None


def test_generic_alarm_sends_l3_and_fallback_to_hist_and_counts_as_a_drift_exit():
    a = L.Setup(mode="MODEL", case="A", holdout_passed=True, fallback_g2_holdout=True)
    st = L.next_state(L.initial_state(a, now_ms=0), a, health=L.Health(), mon=_mon(160), now_ms=1)
    assert st.state == "L3_LIVE"
    h = L.next_state(st, a, health=L.Health(), mon=_mon(200), generic_alarm=True, now_ms=2)
    assert h.state == "HIST" and h.reason == "generic_drift" and h.drift_exits == 1
    b = L.Setup(mode="MODEL", case="B", fallback_g2_holdout=True)
    fb = L.initial_state(b, now_ms=0)
    assert L.next_state(fb, b, health=L.Health(), mon=_mon(100), generic_alarm=True, now_ms=1).state == "HIST"
    # HIST from the held-out stays HIST under an alarm
    hh = L.initial_state(L.Setup(mode="MODEL", case="A"), now_ms=0)
    assert L.next_state(hh, L.Setup(mode="MODEL", case="A"), health=L.Health(), generic_alarm=True, now_ms=1) == hh


def test_generic_return_needs_the_alarm_cleared_and_the_class_recovered():
    a = L.Setup(mode="MODEL", case="A", holdout_passed=True, fallback_g2_holdout=True)
    st = L.next_state(L.initial_state(a, now_ms=0), a, health=L.Health(), mon=_mon(160), now_ms=1)
    h = L.next_state(st, a, health=L.Health(), mon=_mon(200), generic_alarm=True, now_ms=2)
    # class recovered but alarm still on → stays
    assert L.next_state(h, a, health=L.Health(), mon=_mon(260, n_epoch=60, d1=0.3), generic_alarm=True,
                        now_ms=3).state == "HIST"
    # alarm cleared but the class not recovered (too few events / e ≥ 1) → stays
    assert L.next_state(h, a, health=L.Health(), mon=_mon(230, n_epoch=30, d1=0.3), now_ms=3).state == "HIST"
    assert L.next_state(h, a, health=L.Health(), mon=_mon(260, n_epoch=60, d1=2.0), now_ms=3).state == "HIST"
    back = L.next_state(h, a, health=L.Health(), mon=_mon(260, n_epoch=60, d1=0.3), now_ms=4)
    assert back.state == "L3_LIVE"
    # the second exit (any kind) is final
    h2 = L.next_state(back, a, health=L.Health(), mon=_mon(300), generic_alarm=True, now_ms=5)
    assert h2.drift_exits == 2
    assert L.next_state(h2, a, health=L.Health(), mon=_mon(500, n_epoch=200, d1=0.1), now_ms=6).state == "HIST"


def test_generic_monitor_alarm_and_clear():
    rng = np.random.default_rng(15)
    calm = _recs(1500, rng, cls="GENERIC", per_week=40)
    for r in calm:
        r["p_ref"] = r["p_pub"]
    g = L.next_generic_state(L.GenericState(), calm, now_ms=1)
    assert not g.alarm
    drift = calm + [dict(r, p_ref=r["p_pub"]) for r in _recs(400, rng, cls="GENERIC", per_week=40, shift_r=-0.9, t0=40 * WEEK)]
    g = L.next_generic_state(L.GenericState(), drift, now_ms=2)
    assert g.alarm and g.epoch_start == len(drift)
    assert L.next_generic_state(g, drift + calm[:30], now_ms=3).alarm          # < 50 since the alarm
    cleared = L.next_generic_state(g, drift + calm[:300], now_ms=4)
    assert not cleared.alarm
    assert L.generic_monitor_rows([{"t_ms": 0, "pair": (1, 1)}, {"t_ms": 3_600_000, "pair": (1, 1)},
                                   {"t_ms": 0, "pair": (1, 2)}]) == [{"t_ms": 0, "pair": (1, 1)}]


def test_changepoint_mixture_null_false_alarm():
    rng = np.random.default_rng(16)
    hits = 0
    for _ in range(60):
        rows = _recs(1200, rng, cls="GENERIC", per_week=40)
        hits += float(L.changepoint_paths(rows, "p_pub").max()) > L.GEN_THRESHOLD
    assert hits / 60 <= 0.15                      # Ville: ≤ 3 × 1/30 = 0.1; 60 reps carry ±0.04 noise
