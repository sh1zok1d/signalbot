"""Sequence classes, paired inference, and the refusal to reread. No market sequence is read."""

from pathlib import Path

import numpy as np

from scripts.research.level_break_reject_sequence_discovery_v1 import claim, inference, sequence
from scripts.research.level_break_reject_sequence_discovery_v1 import constants as K
from scripts.research.level_break_reject_sequence_discovery_v1.analyze import should_scan
from scripts.research.level_break_reject_sequence_discovery_v1.cohort import gate_from_counts
from scripts.research.level_break_reject_sequence_discovery_v1.evaluate import refuse_if_recorded
from scripts.research.level_touch_degradation_v1.outcomes import classify


def _grid(n=80):
    return np.full(n, 100.0), np.full(n, 100.0)


def _paint(high, low, index, *, break_hit=False, reject_hit=False, side=1):
    if side > 0:
        if break_hit:
            high[index] = 103.0
        if reject_hit:
            low[index] = 97.0
    else:
        if break_hit:
            low[index] = 90.0
        if reject_hit:
            high[index] = 110.0


def _expected(fb, fr):
    if fb is None and fr is None:
        return "NEITHER", None
    if fb is not None and fr is not None and fb == fr:
        return "FIRST_AMBIGUOUS", None
    if fr is None or (fb is not None and fb < fr):
        if fr is None:
            return "BREAK_NO_LATER_REJECT", None
        return "BREAK_THEN_REJECT", 5 * (fr - fb)
    if fb is None:
        return "REJECT_NO_LATER_BREAK", None
    return "REJECT_THEN_BREAK", 5 * (fb - fr)


def _row(high, low, j=10, side=1):
    return sequence.sequence_class(high, low, j, side, 99.0, 101.0, 0.01)


def test_frozen_scales_and_exposure():
    assert K.HORIZON_BARS == 48
    assert K.PRACTICAL_PP == 0.05
    assert K.FDR_Q == 0.10
    assert K.BOOT_DRAWS == 2000
    assert K.BOOT_SEED == 20261022
    assert K.DENOM_GATE == 300
    assert K.FIRST_EVENT_TYPE_ALREADY_EXPOSED is True
    assert K.POST_FIRST_OPPOSITE_BARRIER_SEQUENCE_NOT_YET_READ is True
    assert len(K.CLASSES) == 6


def test_six_classes_are_exhaustive_and_exclusive():
    seen = set()
    for fb in (None, 0, 1, 2):
        for fr in (None, 0, 1, 2):
            high, low = _grid()
            if fb is not None:
                _paint(high, low, 11 + fb, break_hit=True)
            if fr is not None:
                _paint(high, low, 11 + fr, reject_hit=True)
            row = _row(high, low)
            name, delay = _expected(fb, fr)
            assert row["status"] == "OK"
            assert row["class"] == name
            assert row["delay_min"] == delay
            assert sum(row["class"] == item for item in K.CLASSES) == 1
            parent = classify(high, low, 10, 1, 99.0, 101.0, 0.01, 48)
            assert row["first"] == parent
            seen.add(name)
    assert seen == set(K.CLASSES)


def test_later_bar_that_hits_both_counts_as_the_opposite():
    high, low = _grid()
    _paint(high, low, 12, break_hit=True)
    _paint(high, low, 16, break_hit=True, reject_hit=True)
    row = _row(high, low)
    assert row["class"] == "BREAK_THEN_REJECT"
    assert row["delay_min"] == 20
    high, low = _grid()
    _paint(high, low, 12, reject_hit=True)
    _paint(high, low, 16, break_hit=True, reject_hit=True)
    row = _row(high, low)
    assert row["class"] == "REJECT_THEN_BREAK"
    assert row["delay_min"] == 20


def test_touch_bar_first_bar_and_horizon_bounds():
    high, low = _grid()
    _paint(high, low, 10, break_hit=True, reject_hit=True)
    row = _row(high, low)
    assert row["class"] == "NEITHER"
    high, low = _grid()
    _paint(high, low, 11, break_hit=True, reject_hit=True)
    row = _row(high, low)
    assert row["class"] == "FIRST_AMBIGUOUS"
    assert sequence.reversal_flag(row["class"], "P1") is None
    assert sequence.reversal_flag(row["class"], "P2") is None
    high, low = _grid()
    _paint(high, low, 11, break_hit=True)
    _paint(high, low, 12, reject_hit=True)
    row = _row(high, low)
    assert row["class"] == "BREAK_THEN_REJECT"
    assert row["delay_min"] == 5
    high, low = _grid(n=80)
    _paint(high, low, 58, break_hit=True)
    row = _row(high, low)
    assert row["class"] == "BREAK_NO_LATER_REJECT"
    high, low = _grid(n=80)
    _paint(high, low, 59, break_hit=True)
    row = _row(high, low)
    assert row["class"] == "NEITHER"
    high, low = _grid(n=80)
    _paint(high, low, 11, break_hit=True)
    _paint(high, low, 59, reject_hit=True)
    row = _row(high, low)
    assert row["class"] == "BREAK_NO_LATER_REJECT"


def test_support_orientation_and_reversal_flags():
    high, low = _grid()
    _paint(high, low, 12, break_hit=True, side=-1)
    _paint(high, low, 15, reject_hit=True, side=-1)
    row = _row(high, low, side=-1)
    assert row["class"] == "BREAK_THEN_REJECT"
    assert row["delay_min"] == 15
    assert sequence.reversal_flag("BREAK_THEN_REJECT", "P1") == 1
    assert sequence.reversal_flag("BREAK_NO_LATER_REJECT", "P1") == 0
    assert sequence.reversal_flag("REJECT_THEN_BREAK", "P2") == 1
    assert sequence.reversal_flag("REJECT_NO_LATER_BREAK", "P2") == 0
    assert sequence.reversal_flag("BREAK_THEN_REJECT", "P2") is None
    assert sequence.reversal_flag("NEITHER", "P1") is None


def test_unusable_window_is_not_a_class():
    high, low = _grid()
    high[11:16] = np.nan
    low[11:16] = np.nan
    row = _row(high, low)
    assert row["status"] == "UNUSABLE"
    assert row["class"] is None
    assert classify(high, low, 10, 1, 99.0, 101.0, 0.01, 48) is None


def test_gate_does_not_lower_300_and_does_not_merge_directions():
    counts = {
        "real": {"BREAK": 299, "REJECT": 300},
        "pseudo": {"BREAK": 300, "REJECT": 300},
    }
    gates = gate_from_counts(counts)
    assert gates == {"P1": False, "P2": True}
    counts["real"]["BREAK"] = 300
    assert gate_from_counts(counts) == {"P1": True, "P2": True}
    assert should_scan("BREAK", {"P1": False, "P2": True}) is False
    assert should_scan("REJECT", {"P1": False, "P2": True}) is True
    assert should_scan("BREAK", {"P1": True, "P2": False}) is True
    assert should_scan("AMBIGUOUS", {"P1": False, "P2": False}) is True


def test_paired_bootstrap_allows_different_first_types():
    weeks = np.array([1, 1])
    real = np.array([1.0, np.nan])
    pseudo = np.array([np.nan, 0.0])
    out = inference.bootstrap_contrast(weeks, real, pseudo, draws=30, seed=K.BOOT_SEED)
    assert out["n_real"] == 1
    assert out["n_pseudo"] == 1
    assert out["delta"] == 1.0
    assert out["bootstrap_valid"] == 30
    weeks = np.array([1, 1, 2, 2, 3, 3])
    real = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.0])
    pseudo = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    out = inference.bootstrap_contrast(weeks, real, pseudo, draws=40, seed=K.BOOT_SEED)
    assert out["n_real"] == 6 and out["n_pseudo"] == 6
    assert out["delta"] > 0.5
    assert out["delta_ci95"][0] > 0
    assert out["p"] < 0.05


def test_bh_and_wald():
    q1, q2 = inference.bh_adjust([0.01, 0.20])
    assert abs(q1 - 0.02) < 1e-12
    assert abs(q2 - 0.20) < 1e-12
    assert inference.wald_p(0.0, 1.0) == 1.0
    assert inference.wald_p(5.0, 1.0) < 1e-6


def test_year_loyo_family_side_rules():
    full = -0.08
    epochs = [
        {"n_real": 40, "n_pseudo": 40, "delta": -0.06},
        {"n_real": 40, "n_pseudo": 40, "delta": -0.05},
        {"n_real": 40, "n_pseudo": 40, "delta": -0.04},
        {"n_real": 40, "n_pseudo": 40, "delta": -0.02},
        {"n_real": 40, "n_pseudo": 40, "delta": 0.01},
    ]
    assert claim.year_stability(full, epochs)["pass"]
    epochs[3]["delta"] = 0.02
    assert not claim.year_stability(full, epochs)["pass"]
    four = epochs[:4]
    four[3]["delta"] = 0.04
    assert claim.year_stability(full, four)["pass"]
    four[3]["delta"] = 0.06
    assert not claim.year_stability(full, four)["pass"]
    assert not claim.year_stability(full, epochs[:2])["pass"]
    three = [
        {"n_real": 40, "n_pseudo": 40, "delta": -0.02},
        {"n_real": 40, "n_pseudo": 40, "delta": -0.03},
        {"n_real": 40, "n_pseudo": 40, "delta": -0.01},
    ]
    assert claim.year_stability(full, three)["pass"]
    three[2]["delta"] = 0.01
    assert not claim.year_stability(full, three)["pass"]
    thin = {"n_real": 10, "n_pseudo": 40, "delta": -0.08}
    assert not claim.year_stability(full, [thin, thin, thin, thin, thin])["pass"]
    loyo = [{"n_real": 80, "n_pseudo": 80, "delta": -0.04} for _ in range(5)]
    assert claim.loyo_stability(full, loyo)["pass"]
    loyo[0]["delta"] = 0.01
    assert not claim.loyo_stability(full, loyo)["pass"]
    assert not claim.loyo_stability(full, loyo[:2])["pass"]
    families = [
        {"name": "DAY", "n_real": 80, "n_pseudo": 80, "delta": -0.08},
        {"name": "WEEK", "n_real": 40, "n_pseudo": 40, "delta": 0.06},
        {"name": "MONTH", "n_real": 5, "n_pseudo": 5, "delta": 0.20},
    ]
    assert not claim.family_stability(families)["pass"]
    families[1]["delta"] = 0.04
    assert claim.family_stability(families)["pass"]
    sides = [
        {"name": "resistance", "n_real": 50, "n_pseudo": 50, "delta": -0.08},
        {"name": "support", "n_real": 50, "n_pseudo": 50, "delta": 0.06},
    ]
    assert not claim.side_stability(sides)["pass"]
    sides[1]["delta"] = 0.04
    assert claim.side_stability(sides)["pass"]


def test_candidate_rule_and_routes():
    ok = dict(years_ok=True, loyo_ok=True, family_ok=True, side_ok=True, artifact=False)
    passed = claim.decide_primary("P1", -0.06, (-0.10, -0.02), 0.10, 400, 400, **ok)
    assert passed["candidate"] and passed["class"] == "BREAK_FIRST_ONE_SIDED_CANDIDATE"
    flipped = claim.decide_primary("P1", 0.06, (0.02, 0.10), 0.05, 400, 400, **ok)
    assert flipped["class"] == "BREAK_FIRST_REVERSAL_CANDIDATE"
    reject = claim.decide_primary("P2", 0.07, (0.02, 0.12), 0.04, 400, 400, **ok)
    assert reject["class"] == "REJECT_FIRST_REVERSAL_CANDIDATE"
    small = claim.decide_primary("P2", -0.049, (-0.08, -0.02), 0.01, 400, 400, **ok)
    assert not small["candidate"] and small["class"] == "NONE"
    q_fail = claim.decide_primary("P1", -0.08, (-0.12, -0.04), 0.11, 400, 400, **ok)
    assert not q_fail["statistical"] and not q_fail["candidate"] and not q_fail["information_limited"]
    wide = claim.decide_primary("P1", 0.08, (0.01, 0.30), 0.01, 400, 400, **ok)
    assert wide["candidate"] and not wide["information_limited"]
    assert claim.material(0.05) and not claim.material(0.049)
    assert claim.route(
        [], novelty_ok=False, any_gate=True,
    ) == "BLOCKED_REOPENING_FAILED_BREAKOUT_SEQUENCE"
    assert claim.route([], novelty_ok=True, any_gate=False) == "INFORMATION_LIMITED"
    assert claim.route(
        [{"estimated": True, "candidate": True, "statistical": True, "stable": True,
          "information_limited": False}],
        novelty_ok=True, any_gate=True,
    ) == "LEVEL_SEQUENTIAL_OUTCOME_STRUCTURE_PRESENT"
    assert claim.route(
        [{"estimated": True, "candidate": False, "statistical": True, "stable": False,
          "information_limited": False}],
        novelty_ok=True, any_gate=True,
    ) == "STRUCTURE_PRESENT_BUT_UNSTABLE"
    assert claim.route(
        [{"estimated": True, "candidate": False, "statistical": False, "stable": True,
          "information_limited": False}],
        novelty_ok=True, any_gate=True,
    ) == "NO_INCREMENTAL_SEQUENTIAL_OUTCOME_STRUCTURE"
    assert claim.route(
        [
            {"estimated": True, "candidate": False, "statistical": False, "stable": True,
             "information_limited": True},
            {"estimated": True, "candidate": False, "statistical": False, "stable": True,
             "information_limited": False},
        ],
        novelty_ok=True, any_gate=True,
    ) == "NO_INCREMENTAL_SEQUENTIAL_OUTCOME_STRUCTURE"


def test_preflight_cannot_read_the_sequence():
    root = Path("scripts/research/level_break_reject_sequence_discovery_v1")
    preflight = (root / "preflight.py").read_text()
    cohort = (root / "cohort.py").read_text()
    evaluate = (root / "evaluate.py").read_text()
    for banned in ("BREAK_THEN_REJECT", "sequence_class", "reversal_flag", "import sequence"):
        assert banned not in preflight
        assert banned not in cohort
    assert "from .sequence" not in preflight
    assert "from .analyze import run" not in evaluate.split("def main")[0]
    assert "REFUSING_RERUN" in evaluate


def test_refusing_rerun(tmp_path):
    target = tmp_path / "RESULT.json"
    target.write_text("{}")
    try:
        refuse_if_recorded(target, tmp_path / "missing.md")
    except SystemExit as exc:
        assert "REFUSING_RERUN" in str(exc)
    else:
        raise AssertionError("second run was allowed")
