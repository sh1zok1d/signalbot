from __future__ import annotations

import ast
import importlib.util
import math
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "research" / "v2_e1_development_outcomes.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("v2_e1_development_outcomes", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_stage6_imports():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(name.startswith("analytics.forecasting_v2.episode_") for name in imported)
    assert "analytics.forecasting_v2.event_factory" not in imported


def test_directional_return_matches_preregistered_formula():
    m = _load_module()
    assert math.isclose(m._directional_return("LONG", 100.0, 110.0), 0.1)
    assert math.isclose(m._directional_return("SHORT", 100.0, 90.0), 0.1)
    # Explicitly guards against the reciprocal alternative 100/90-1.
    assert not math.isclose(
        m._directional_return("SHORT", 100.0, 90.0),
        100.0 / 90.0 - 1.0,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_final_split_partition_and_four_hour_purge():
    m = _load_module()
    utc = timezone.utc
    assert m._candidate_partition(datetime(2026, 8, 15, 20, 0, tzinfo=utc)) == "DEV_OUTCOME_ELIGIBLE"
    assert m._candidate_partition(datetime(2026, 8, 15, 20, 5, tzinfo=utc)) == "DEV_PURGE"
    assert m._candidate_partition(datetime(2026, 8, 15, 23, 55, tzinfo=utc)) == "DEV_PURGE"
    assert m._candidate_partition(datetime(2026, 8, 16, 0, 0, tzinfo=utc)) == "HOLDOUT_SEALED"


def test_sql_upper_bound_is_parameterized_and_no_now_clock():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "ts < $4" in source
    assert "datetime.now(" not in source
    assert "datetime.utcnow(" not in source
    assert "CURRENT_TIMESTAMP" not in source
    assert " now()" not in source.lower()
