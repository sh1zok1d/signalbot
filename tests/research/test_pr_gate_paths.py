"""CI path-list sanity. Does not run MARKET-01 or mint evidence."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PATHS_FILE = REPO / "scripts" / "ci" / "pr_gate_paths.txt"
PR_GATE_PY = REPO / "scripts" / "ci" / "pr_gate.py"


def _pr_gate():
    spec = importlib.util.spec_from_file_location("signalbot_pr_gate", PR_GATE_PY)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_pr_gate_paths_exist_and_are_nonempty():
    lines = []
    for raw in PATHS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    assert lines, "PR gate path list is empty"
    for item in lines:
        path = item.split("::", 1)[0]
        assert (REPO / path).is_file(), item


def test_large_integration_diff_stays_on_always_list_plus_source_map():
    gate = _pr_gate()
    always = gate._load_always()
    changed = (
        [f"tests/research/test_extra_{i}.py" for i in range(25)]
        + [f"scripts/research/module_{i}.py" for i in range(13)]
        + [
            "scripts/research/market_01_oi_expansion_weak_continuation_lib.py",
            "scripts/research/harness_synthetic_edge_calibration_v1_production.py",
        ]
    )
    targets = gate._select_targets(always, changed)
    assert "tests/research/test_market_01_canonical_result.py" in targets
    assert "tests/research/test_market_01_episode_construction_fast.py" in targets
    assert "tests/research/test_extra_0.py" not in targets
    assert (
        "tests/research/test_harness_synthetic_edge_calibration_v1_production.py"
        not in targets
    )
    mapped = gate._mapped_test_for_source(
        "scripts/research/market_01_oi_expansion_weak_continuation_lib.py"
    )
    if mapped:
        assert mapped in targets
