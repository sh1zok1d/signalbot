from __future__ import annotations

import ast
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "research" / "v2_e1_holdout_ablation_inventory_vps.py"


def test_holdout_ablation_inventory_is_outcome_free_and_frozen_window():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any(name.startswith("scripts.research.v2_e1_development_outcomes") for name in imported)
    assert not any(name.startswith("scripts.research.v2_e1_development_ablation_outcomes") for name in imported)
    assert "2026, 8, 16, 0, 0" in source
    assert "2026, 8, 25, 17, 20" in source
    assert "EXPECTED_BOUNDARIES = 2800" in source
    assert "TP_FULL: 105" in source
    assert "CB_FULL: 17" in source
    assert "FB_FULL: 19" in source
    assert '"outcomes_included"] = False' in source
    assert '"holdout_outcomes_opened"] = False' in source
    assert '"holdout_market_rows_read"] = False' in source
