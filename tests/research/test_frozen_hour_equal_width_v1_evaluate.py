"""Synthetic tests for the equal-width outcome evaluator. No spot file is opened."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from scripts.research.frozen_hour_equal_width_v1 import census, evaluate
from scripts.research.frozen_hour_equal_width_v1.evaluate import (
    _one_mean,
    cell_clears,
    descriptive_neither_immediate,
    resolution_indicator,
    route_name,
)
from scripts.research.opening_range_object_v1.outcomes import score_window

ROOT = Path(__file__).resolve().parents[2]
CENSUS_COMMIT = "3b02de8380064aa2ce3fe384e86899e08d2b3778"


def test_resolution_matches_the_parent_indicator_and_uses_arm_width():
    quiet_high = np.full(48, 105.0)
    quiet_low = np.full(48, 101.0)
    assert resolution_indicator(quiet_high, quiet_low, 110.0, 90.0, "high") == 0.0
    extended = quiet_high.copy()
    extended[3] = 130.0
    assert resolution_indicator(extended, quiet_low, 110.0, 90.0, "high") == score_window(
        extended, quiet_low, 110.0, 90.0, "high"
    )["resolution"]
    reentry_low = quiet_low.copy()
    reentry_low[2] = 90.0
    assert resolution_indicator(quiet_high, reentry_low, 110.0, 90.0, "high") == 1.0
    low_side_high = np.full(48, 99.0)
    low_side_low = np.full(48, 95.0)
    low_side_low[1] = 70.0
    assert resolution_indicator(low_side_high, low_side_low, 110.0, 90.0, "low") == 1.0
    narrow_high = np.full(48, 105.0)
    narrow_low = np.full(48, 101.0)
    narrow_high[0] = 112.0
    assert resolution_indicator(narrow_high, narrow_low, 110.0, 90.0, "high") == 0.0
    assert resolution_indicator(narrow_high, narrow_low, 105.0, 95.0, "high") == 1.0


def test_bootstrap_weight_and_clear_rule():
    assert _one_mean({"w0": (1.0, 1), "w1": (0.0, 1)}, {"w0": 2, "w1": 0}) == 1.0
    assert _one_mean({"w0": (1.0, 1), "w1": (0.0, 1)}, {"w0": 1, "w1": 1}) == 0.5
    assert cell_clears(0.04, {"interpretable": True, "lo": 0.01, "hi": 0.05}) is True
    assert cell_clears(0.04, {"interpretable": True, "lo": -0.01, "hi": 0.05}) is False
    assert cell_clears(0.02, {"interpretable": True, "lo": 0.01, "hi": 0.03}) is False
    assert cell_clears(-0.04, {"interpretable": True, "lo": -0.06, "hi": -0.02}) is True
    assert cell_clears(0.05, {"interpretable": False, "lo": None, "hi": None}) is False
    assert route_name(True, support_ok=True) == "WIDTH_HELD_DIFFERENCE_PRESENT"
    assert route_name(False, support_ok=True) == "NO_WIDTH_HELD_RESOLUTION_DIFFERENCE"
    assert route_name(True, support_ok=False) == "INFORMATION_LIMITED_STOP_BEFORE_OUTCOME"


def test_neither_immediate_mean_is_not_a_route_input():
    rows = [
        {"delta": 1.0, "real_immediate": False, "pseudo_immediate": False},
        {"delta": 0.0, "real_immediate": True, "pseudo_immediate": False},
    ]
    short = descriptive_neither_immediate(rows * 14)
    assert short["n"] == 14 and short["printed"] is False and short["paired_mean"] is None
    long = descriptive_neither_immediate(rows * 30)
    assert long["n"] == 30 and long["printed"] is True and long["paired_mean"] == 1.0
    assert route_name(False, support_ok=True) == "NO_WIDTH_HELD_RESOLUTION_DIFFERENCE"


def test_support_file_guard_and_rerun_refuse_before_load(tmp_path, monkeypatch):
    frozen = json.loads(
        (ROOT / "docs/research/FROZEN_HOUR_EQUAL_WIDTH_V1_FEASIBILITY.json").read_text(encoding="utf-8")
    )
    evaluate.require_frozen_support_file(frozen)
    broken = json.loads(json.dumps(frozen))
    broken["cells"]["UTC_00"]["paired_outcome_eligible"] = 1
    with pytest.raises(SystemExit) as exc:
        evaluate.require_frozen_support_file(broken)
    assert str(exc.value) == "SUPPORT_MISMATCH_STOP_BEFORE_Y"
    live = json.loads(json.dumps(frozen))
    live["cells"]["UTC_12"]["paired_iso_weeks"] = 1
    with pytest.raises(SystemExit) as mismatch:
        evaluate.require_live_matches(live, frozen)
    assert str(mismatch.value) == "SUPPORT_MISMATCH_STOP_BEFORE_Y"
    monkeypatch.setattr(evaluate, "RESULT_JSON", tmp_path / "result.json")
    monkeypatch.setattr(evaluate, "RESULT_MD", tmp_path / "result.md")
    monkeypatch.setattr(evaluate, "MANIFEST_PATH", tmp_path / "manifest.json")
    (tmp_path / "result.json").write_text("{}", encoding="utf-8")

    def _boom():
        raise AssertionError("rerun opened the market")

    monkeypatch.setattr("scripts.research.frozen_hour_equal_width_v1.data.load_panel", _boom)
    with pytest.raises(SystemExit) as rerun:
        evaluate.main()
    assert str(rerun.value) == "REFUSING_RERUN"


def test_loader_and_solver_match_the_support_commit():
    for rel in (
        "scripts/research/frozen_hour_equal_width_v1/data.py",
        "scripts/research/frozen_hour_equal_width_v1/solver.py",
        "scripts/research/frozen_hour_equal_width_v1/constants.py",
        "scripts/research/frozen_hour_equal_width_v1/__init__.py",
    ):
        committed = subprocess.check_output(["git", "show", f"{CENSUS_COMMIT}:{rel}"], cwd=ROOT)
        current = (ROOT / rel).read_bytes()
        assert hashlib.sha256(committed).hexdigest() == hashlib.sha256(current).hexdigest()


def test_official_outcome_is_the_null_route_and_refuses_rerun(monkeypatch):
    manifest = json.loads(
        (ROOT / "docs/research/FROZEN_HOUR_EQUAL_WIDTH_V1_EVALUATOR_MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    result = json.loads(
        (ROOT / "docs/research/FROZEN_HOUR_EQUAL_WIDTH_V1_RESULT.json").read_text(encoding="utf-8")
    )
    assert manifest["pre_outcome_evaluator_commit"] == "c51e7da046c785861877de9b5aa0ebea5a9a86a5"
    assert manifest["code_digest"] == census.code_digest()
    assert manifest["code_digest"] == "846c784c9bb09f6c236cc3ef31407301235cf03984e97fed9236e14477037303"
    assert manifest["route"] == result["route"] == "NO_WIDTH_HELD_RESOLUTION_DIFFERENCE"
    assert result["outcome_read"] is True
    assert result["successor_started"] is False
    utc_00 = result["cells"]["UTC_00"]
    utc_12 = result["cells"]["UTC_12"]
    assert (utc_00["n"], utc_00["iso_weeks"], utc_00["clears"]) == (817, 123, False)
    assert (utc_12["n"], utc_12["iso_weeks"], utc_12["clears"]) == (833, 123, False)
    assert utc_12["role"] == "diagnostic_not_adoptable"

    def _boom():
        raise AssertionError("official rerun opened the market")

    monkeypatch.setattr("scripts.research.frozen_hour_equal_width_v1.data.load_panel", _boom)
    with pytest.raises(SystemExit) as rerun:
        evaluate.main()
    assert str(rerun.value) == "REFUSING_RERUN"


def test_pair_sink_matches_the_support_count():
    n = 14 * 288
    high = np.full(n, np.nan)
    low = np.full(n, np.nan)
    close = np.full(n, np.nan)
    from tests.research.test_frozen_hour_equal_width_v1_census import _paint

    _paint(high, low, close, 1, 110.0, 90.0, 100.0, 10, 1.0e6, 100.0)
    _paint(high, low, close, 8, 104.0, 97.0, 100.0, 10, 1.0e6, 100.0)
    t0 = census._ms("2018-01-01") if hasattr(census, "_ms") else 1514764800000
    from scripts.research.frozen_hour_equal_width_v1 import constants as K
    t0 = K._ms("2018-01-01")
    sink = []
    counts = census._cell(high, low, close, t0, 0, sink)
    plain = census._cell(high, low, close, t0, 0)
    assert counts["paired_outcome_eligible"] == plain["paired_outcome_eligible"] == len(sink)
    assert sink
    scored = evaluate.score_pairs(high, low, sink)
    assert len(scored) == len(sink)
    assert set(row["y_real"] for row in scored) <= {0.0, 1.0}
