from __future__ import annotations

import ast
import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "research" / "v2_e1_development_controls.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("v2_e1_development_controls", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_stage6_imports_and_holdout_upper_bound_is_parameterized():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(name.startswith("analytics.forecasting_v2.episode_") for name in imported)
    assert "analytics.forecasting_v2.event_factory" not in imported
    source = SCRIPT.read_text(encoding="utf-8")
    assert "ts < $4" in source
    assert "datetime.now(" not in source
    assert "datetime.utcnow(" not in source


def test_family_decision_clocks_are_frozen():
    m = _load_module()
    utc = timezone.utc
    assert m._family_clock_ok("TREND_PULLBACK", datetime(2026, 8, 10, 12, 0, tzinfo=utc))
    assert m._family_clock_ok("TREND_PULLBACK", datetime(2026, 8, 10, 12, 15, tzinfo=utc))
    assert not m._family_clock_ok("TREND_PULLBACK", datetime(2026, 8, 10, 12, 5, tzinfo=utc))
    assert m._family_clock_ok("COMPRESSION_BREAKOUT", datetime(2026, 8, 10, 12, 5, tzinfo=utc))
    assert m._family_clock_ok("CONFIRMED_BREAKOUT", datetime(2026, 8, 10, 12, 55, tzinfo=utc))


def test_direction_inversion_is_exact():
    m = _load_module()
    assert m._opposite("LONG") == "SHORT"
    assert m._opposite("SHORT") == "LONG"


def test_group_seed_is_stable_and_group_specific():
    m = _load_module()
    day = date(2026, 8, 10)
    a = m._stable_group_seed(20260825, "TREND_PULLBACK", day)
    b = m._stable_group_seed(20260825, "TREND_PULLBACK", day)
    c = m._stable_group_seed(20260825, "COMPRESSION_BREAKOUT", day)
    assert a == b
    assert a != c


def test_day_grid_respects_trend_pullback_15m_clock():
    m = _load_module()
    grid = list(m._iter_day_grid(date(2026, 8, 10), "TREND_PULLBACK"))
    assert len(grid) == 96
    assert all(T.minute % 15 == 0 for T in grid)
