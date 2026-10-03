"""Persisted-record integrity for SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0.

The committed result binds the frozen design, runner and library. It keeps
the protected-surface flags and carries no E-versus-S outcome statistic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "research" / "SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0_DESIGN.json"
RESULT = ROOT / "docs" / "research" / "SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0.json"
RUNNER = ROOT / "scripts" / "research" / "selling_exhaustion_support_feasibility_v0.py"
LIB = ROOT / "scripts" / "research" / "selling_exhaustion_support_feasibility_v0_lib.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _keys(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, out)
    return out


def test_result_binds_the_frozen_design_and_code():
    res = json.loads(RESULT.read_text())
    assert res["DESIGN_SHA256"] == _sha(DESIGN)
    assert res["RUNNER_SHA256"] == _sha(RUNNER)
    assert res["LIB_SHA256"] == _sha(LIB)
    design = json.loads(DESIGN.read_text())
    for rel, digest in design["CODE_IDENTITY"].items():
        assert _sha(ROOT / rel) == digest, rel


def test_result_keeps_flags_and_surface():
    res = json.loads(RESULT.read_text())
    assert res["STAGE"] == "FEASIBILITY_ONLY"
    assert res["E1_INTERVAL_TOUCHED"] is False
    assert res["E_MINUS_S_OUTCOME_CONTRAST_COMPUTED"] is False
    assert res["SEED_CREATED"] is False
    assert res["PROSPECTIVE_ACTIVATED"] is False
    assert res["PIT_AUDIT_OK"] is True
    assert res["SURFACE"]["DECISIONS_UTC"] == ["2023-01-01T00:00:00Z", "2026-08-11T00:00:00Z"]
    assert res["SURFACE"]["READ_HORIZON_EXCLUSIVE_UTC"] == "2026-08-15T00:00:00Z"
    assert res["VERDICT_BINARY_PRIMARY"] == {"STATUS": "INFORMATIONALLY_WEAK",
                                             "REASONS": ["NOT_TESTABLE_WITHIN_REALISTIC_HORIZON"]}


def test_real_outcomes_appear_only_in_the_state_blind_block():
    res = json.loads(RESULT.read_text())
    dep = res["OUTCOME_DEPENDENCE_STATE_BLIND"]
    assert dep["STATE_BLIND"] is True
    rest = {k: v for k, v in res.items() if k != "OUTCOME_DEPENDENCE_STATE_BLIND"}
    keys = _keys(rest)
    assert not any("Y1_48H" in k or k.endswith("_RATE") and "POPULATION" in k for k in keys)
    assert "SUPPORT_POPULATION_Y1_48H_RATE" in dep
    for variant in res["PER_VARIANT"].values():
        assert set(variant["LAYOUT"]["E"]) >= {"EPISODES", "WEEK_CLUSTERS"}
        assert not any("WIN" in k or "LOSS" in k for k in _keys(variant))
