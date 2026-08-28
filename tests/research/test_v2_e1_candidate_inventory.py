from __future__ import annotations

import ast
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "research" / "v2_e1_candidate_inventory.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("v2_e1_candidate_inventory", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_e1_candidate_inventory_imports_no_stage6_or_outcome_modules():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = sorted(
        name for name in imported
        if name.startswith("analytics.forecasting_v2.episode_")
        or name == "analytics.forecasting_v2.event_factory"
        or name.startswith("analytics.forecasting.outcomes")
    )
    assert forbidden == []

    source = SCRIPT.read_text(encoding="utf-8")
    assert "evaluate_early_signal_transition(" not in source
    assert "build_episode_transition_event(" not in source


def test_boundary_iterator_is_exact_start_inclusive_end_exclusive():
    module = _load_script_module()
    start = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 25, 12, 15, tzinfo=timezone.utc)
    assert list(module._iter_boundaries(start, end)) == [
        datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 25, 12, 5, tzinfo=timezone.utc),
        datetime(2026, 8, 25, 12, 10, tzinfo=timezone.utc),
    ]


def test_parse_utc_refuses_rounding_or_non_utc_inputs():
    module = _load_script_module()
    assert module._parse_utc("2026-08-25T12:10:00Z") == datetime(
        2026, 8, 25, 12, 10, tzinfo=timezone.utc)
    with pytest.raises(Exception):
        module._parse_utc("2026-08-25T12:11:00Z")
    with pytest.raises(Exception):
        module._parse_utc("2026-08-25T15:10:00+03:00")


def test_json_output_preserves_bool_vs_int_type():
    module = _load_script_module()
    payload = module._jsonable({"bool_value": True, "int_value": 1})
    encoded = json.dumps(payload, sort_keys=True)
    assert payload["bool_value"] is True
    assert type(payload["int_value"]) is int
    assert '"bool_value": true' in encoded
    assert '"int_value": 1' in encoded
