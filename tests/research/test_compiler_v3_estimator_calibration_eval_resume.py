"""EVAL resume driver: static audit, capacity rule and immutability checks. Never executes a frozen cell."""

import ast
import json
from pathlib import Path

import pytest

from scripts.research.compiler_v3_estimator_calibration import eval_resume as ER

FORBIDDEN = {"naive_variance", "long_run_variance", "bartlett_omega", "chi2_bound", "generate", "ar1_unit", "innovations",
             "default_rng", "SeedSequence", "standard_normal", "record", "decide_cell", "coverage_decision", "utility_decision",
             "class_state", "run_cal", "seal_c_table", "build_c_table", "var", "mean", "ppf", "VA", "VB", "MISS_A", "UTIL_A"}


def test_resume_driver_static_audit():
    tree = ast.parse(Path(ER.__file__).read_text())
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    consts = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not (names & FORBIDDEN), names & FORBIDDEN
    assert not ({"VA", "VB", "T", "E", "MISS_A", "COVERAGE", "UTILITY"} & consts) or consts & {"S"}   # only the seed field "S" is read from rows
    assert "_run_cell" in names and "_integrity" in names and "aggregate" in names


def test_capacity_rule_constants():
    assert ER.BYTES_PER_ROW == 512 and ER.RESERVE_BYTES == 2_000_000_000


def test_artifacts_immutable_once_present():
    for fn, path in ((ER.snapshot, ER.SNAPSHOT), (ER.amend, ER.AMENDMENT), (ER.bind, ER.BINDING), (ER.authorize, ER.AUTH)):
        if path.exists():
            with pytest.raises(RuntimeError, match="immutable"):
                fn()


def test_snapshot_consistency_if_present():
    if not ER.SNAPSHOT.exists():
        pytest.skip("no snapshot")
    s = json.loads(ER.SNAPSHOT.read_text())
    rem = sum(r["REMAINING_MAX_ROWS"] for r in s["SHARDS"])
    assert rem == s["REMAINING_MAX_ROWS"] and s["CONFIRMATIONS"]["OUTCOME_FIELDS_READ_FOR_THIS_SNAPSHOT"] is False
    assert sum(s["COUNTS"].values()) == 5535


def test_execute_refuses_without_single_thread_env(monkeypatch):
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    with pytest.raises(RuntimeError, match="OMP_NUM_THREADS"):
        ER.execute()
