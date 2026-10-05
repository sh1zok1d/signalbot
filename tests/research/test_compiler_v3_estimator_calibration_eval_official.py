"""Official EVAL driver: static audit, surface expectation and immutability checks. Never executes a frozen cell."""

import ast
import json
from pathlib import Path

import pytest

from scripts.research.compiler_v3_estimator_calibration import eval_official as EO

FORBIDDEN = {"naive_variance", "long_run_variance", "bartlett_omega", "chi2_bound", "generate", "ar1_unit", "innovations",
             "default_rng", "SeedSequence", "standard_normal", "record", "decide_cell", "coverage_decision", "utility_decision",
             "class_state", "run_cal", "seal_c_table", "build_c_table", "var", "mean", "ppf"}


def test_driver_static_audit_no_research_logic():
    tree = ast.parse(Path(EO.__file__).read_text())
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not (names & FORBIDDEN), names & FORBIDDEN
    assert "run_eval" in names and "aggregate" in names


def test_eval_surface_expectation():
    s = EO.eval_surface()
    assert s["CELLS"] == 5535 and s["STAGE_A_REPLICATES"] == 22_140_000 and s["BY_SOURCE"] == {"GRID_621": 621, "PROBES_198": 198, "DENSE_4716": 4716}


def test_binding_and_authorization_immutable_once_present():
    if EO.EVAL_BINDING.exists():
        with pytest.raises(RuntimeError, match="immutable"):
            EO.bind()
        b = json.loads(EO.EVAL_BINDING.read_text())
        assert b["DRIVER"]["SHA256"] == EO.sha(EO.DRIVER) and b["EVAL_SURFACE"]["CELLS"] == 5535
    if EO.EVAL_AUTH.exists():
        with pytest.raises(RuntimeError, match="immutable"):
            EO.authorize()


def test_execute_refuses_without_single_thread_env(monkeypatch):
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    # the closed-line guard refuses first; the frozen driver's own check is exercised on the original
    with pytest.raises(RuntimeError, match="OMP_NUM_THREADS"):
        EO.execute.__wrapped__()
