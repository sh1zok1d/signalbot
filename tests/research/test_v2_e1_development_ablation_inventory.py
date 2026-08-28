from __future__ import annotations

import ast
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "research" / "v2_e1_development_ablation_inventory.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("v2_e1_development_ablation_inventory", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_contains_no_outcome_or_stage6_imports():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "scripts.research.v2_e1_development_outcomes" not in imported
    assert "scripts.research.v2_e1_development_controls" not in imported
    assert not any(name.startswith("analytics.forecasting_v2.episode_") for name in imported)
    assert "analytics.forecasting_v2.event_factory" not in imported


def test_window_is_exact_frozen_development_window():
    m = _load_module()
    utc = timezone.utc
    assert m.DEV_START == datetime(2026, 8, 2, 0, 0, tzinfo=utc)
    assert m.HOLDOUT_START == datetime(2026, 8, 16, 0, 0, tzinfo=utc)
    boundaries = tuple(m._iter_boundaries())
    assert len(boundaries) == 14 * 24 * 12
    assert boundaries[0] == m.DEV_START
    assert boundaries[-1] < m.HOLDOUT_START


def test_fb_dumb_is_explicit_alias_population_name():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'variant=FB_NO_CONTEXT' in source
    assert 'variant=FB_DUMB' in source
    assert "exact Stage-5 population alias of FB_NO_CONTEXT" in source


def test_no_wall_clock_or_random_parameter_search():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "datetime.now(" not in source
    assert "datetime.utcnow(" not in source
    assert "random." not in source
    assert "numpy" not in source
