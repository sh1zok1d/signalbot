"""Persisted-record integrity for DIVERGENCE_FULL_HISTORY_RESEARCH_V0.

Checks that the committed stage-1 and stage-2 records bind the frozen design,
the frozen runner and each other, and keep the protected-surface flags.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = ROOT / "docs" / "research"
DESIGN = RESEARCH_DIR / "DIVERGENCE_FULL_HISTORY_RESEARCH_V0_DESIGN.json"
VALIDATION = RESEARCH_DIR / "DIVERGENCE_FULL_HISTORY_RESEARCH_V0_VALIDATION.json"
RESEARCH = RESEARCH_DIR / "DIVERGENCE_FULL_HISTORY_RESEARCH_V0_RESEARCH.json"
RUNNER = ROOT / "scripts" / "research" / "divergence_full_history_v0.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_design_code_identity_still_matches():
    design = _load(DESIGN)
    for rel, digest in design["CODE_IDENTITY"].items():
        assert _sha(ROOT / rel) == digest, rel


def test_validation_record_binds_design_runner_and_episodes():
    val = _load(VALIDATION)
    assert val["DESIGN_SHA256"] == _sha(DESIGN)
    assert val["RUNNER_SHA256"] == _sha(RUNNER)
    assert val["VALIDATION_EPISODES_SHA256"] == _sha(ROOT / val["VALIDATION_EPISODES_CSV"])
    assert val["EVALUATED_ONCE"] is True
    assert val["E1_INTERVAL_TOUCHED"] is False
    assert val["PROSPECTIVE_ACTIVATED"] is False
    assert val["SEED0003_CREATED"] is False
    assert val["READ_HORIZON_EXCLUSIVE_UTC"] == "2026-08-15T00:00:00Z"


def test_research_record_binds_validation_and_stays_exploratory():
    res = _load(RESEARCH)
    assert res["VALIDATION_RESULT_SHA256"] == _sha(VALIDATION)
    assert res["DESIGN_SHA256"] == _sha(DESIGN)
    assert res["RUNNER_SHA256"] == _sha(RUNNER)
    assert "never independent replication or confirmation" in res["LABEL"]
    assert res["E1_INTERVAL_TOUCHED"] is False
    assert res["PROSPECTIVE_ACTIVATED"] is False
    assert res["SEED0003_CREATED"] is False
