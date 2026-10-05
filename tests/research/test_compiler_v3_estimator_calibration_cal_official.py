"""Official CAL driver: static and refusal checks only. Never touches the official run directory."""

import ast
import os
from pathlib import Path

import pytest

from scripts.research.compiler_v3_estimator_calibration import cal_official as CO


def test_driver_has_no_eval_entry_point():
    src = Path(CO.__file__).read_text()
    tree = ast.parse(src)
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "run_eval" not in names and "eval_gate" not in names and "eval_replicate" not in names


def test_execute_refuses_without_single_thread_env(monkeypatch):
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    with pytest.raises(RuntimeError, match="OMP_NUM_THREADS"):
        CO.execute()


def test_step_artifacts_are_immutable():
    for fn, path in ((CO.bind, CO.BINDING), (CO.authorize, CO.CAL_AUTH)):
        if path.exists():
            with pytest.raises(RuntimeError, match="immutable"):
                fn()
