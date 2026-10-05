"""Operational tombstone of the CLOSED compiler V3 variance line.

Every refusal test also replaces the original function behind the guard with a tripwire, so a
failing guard can never start an official run from this suite."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.research import closed_lines as CL

REPO = Path(__file__).resolve().parents[2]
LINE = next(line for line in CL.registry()["LINES"] if line["LINE_ID"] == "COMPILER_V3_VARIANCE")


def _tripwire(*_a, **_k):
    raise AssertionError("closed-line guard let an official entry point through")


def test_registry_points_at_existing_closure_and_no_reopen_authorization():
    assert LINE["STATUS"] == "CLOSED"
    assert (REPO / LINE["CLOSURE_RECORD"]).exists()
    assert not (REPO / LINE["REOPEN_AUTHORIZATION_PATH"]).exists()
    for spec in LINE["ENTRYPOINTS"]:
        assert not CL.reopen_authorized(LINE, f"{spec['MODULE']}.{spec['FUNCTION']}")


def test_frozen_files_untouched_by_the_guard():
    """The guard lives in __init__.py only; the bound executor files keep their recorded digests."""
    from scripts.research.compiler_v3_variance_floor import freeze
    freeze.verify_execution_binding()                      # raises on any bound-file digest change
    from scripts.research.compiler_v3_estimator_calibration import engine
    binding = json.loads((REPO / "docs/research/COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_EVAL_BINDING_V1.json").read_text())
    assert engine.executor_digest()["EXECUTOR_DIGEST"] == binding["EXECUTOR"]["EXECUTOR_DIGEST"]


def test_variance_floor_official_run_refused(monkeypatch):
    from scripts.research.compiler_v3_variance_floor import engine
    monkeypatch.setattr(engine.official_run, "__wrapped__", _tripwire)
    with pytest.raises(CL.ClosedResearchLineError, match="CLOSED") as exc:
        engine.official_run()
    assert isinstance(exc.value, engine.OfficialRunNotAuthorized)


def test_estimator_official_phases_refused_even_with_thread_env(monkeypatch, tmp_path):
    from scripts.research.compiler_v3_estimator_calibration import cal_official, cells, engine, eval_official, eval_resume
    for k, v in eval_official.THREAD_ENV.items():          # the frozen drivers' own first check would pass
        monkeypatch.setenv(k, v)
    for mod in (cal_official, eval_official, eval_resume):
        monkeypatch.setattr(mod.execute, "__wrapped__", _tripwire)
        with pytest.raises(CL.ClosedResearchLineError, match="CLOSED"):
            mod.execute()
    for fn in (engine.run_cal, engine.run_eval):
        monkeypatch.setattr(fn, "__wrapped__", _tripwire)
    with pytest.raises(engine.OfficialExecutionRefused, match="CLOSED"):
        engine.run_cal(tmp_path, cells.cal_cells()[:1], cal_n=1, official=True)
    with pytest.raises(engine.OfficialExecutionRefused, match="CLOSED"):
        engine.run_eval(tmp_path, [], official=True)


def test_non_official_paths_pass_through(monkeypatch, tmp_path):
    from scripts.research.compiler_v3_estimator_calibration import engine
    seen = []
    monkeypatch.setattr(engine.run_cal, "__wrapped__", lambda *a, **k: seen.append(k.get("official", False)))
    engine.run_cal(tmp_path, [], cal_n=1)
    assert seen == [False]


@pytest.mark.parametrize("argv, refused", [
    (["python", "-m", "scripts.research.compiler_v3_variance_floor.engine", "--official"], True),
    (["python", "-m", "scripts.research.compiler_v3_variance_floor.engine"], False),
    (["python", "scripts/research/compiler_v3_variance_floor/engine.py", "--official"], True),
    (["python", "-m", "scripts.research.compiler_v3_estimator_calibration.run", "--official", "x"], True),
    (["python", "-m", "scripts.research.compiler_v3_estimator_calibration.run", "--digests"], False),
    (["python", "-m", "scripts.research.compiler_v3_estimator_calibration.cal_official", "execute"], True),
    (["python", "-m", "scripts.research.compiler_v3_estimator_calibration.eval_official", "execute"], True),
    (["python", "-m", "scripts.research.compiler_v3_estimator_calibration.eval_official", "verify-binding"], False),
    (["python", "-m", "scripts.research.compiler_v3_estimator_calibration.eval_resume", "execute"], True),
    (["python", "-m", "pytest", "-q"], False),
])
def test_cli_rules(argv, refused):
    assert (CL.cli_violation(argv, LINE) is not None) == refused


def test_cli_refusal_end_to_end():
    """Real `python -m` invocation; the estimator `run --official` path is also refused by the frozen
    engine itself (no RUN_AUTHORIZATION file), so this subprocess cannot run anything either way."""
    out = subprocess.run([sys.executable, "-m", "scripts.research.compiler_v3_estimator_calibration.run",
                          "--official", "/nonexistent/closed-line-test"],
                         cwd=REPO, capture_output=True, text=True, timeout=120,
                         env={**os.environ, "PYTHONPATH": str(REPO)})
    assert out.returncode != 0 and "is CLOSED" in out.stderr
    assert not Path("/nonexistent/closed-line-test").exists()
