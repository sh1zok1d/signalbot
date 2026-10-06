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


def test_generator_source_or_authority_selects_complete_focused_suite():
    gate = _pr_gate()
    expected = {str(p.relative_to(REPO)) for p in (REPO / 'tests/research').glob('test_generator_v0_*.py')}
    for changed in ('scripts/research/generator_v0/context.py', 'docs/research/MECHANISM_MEMORY_V0.json',
                    'docs/research/generator_v0_memory/HEAD.json'):
        assert expected <= set(gate._select_targets([], [changed]))


def test_c013_bound_paths_select_its_suite():
    for changed in ('scripts/research/gv0r01_c013_market_test_lib.py', 'docs/research/GV0R01_C013_MARKET_TEST_PREREG.json',
                    'docs/research/SCIENTIFIC_TEST_LEDGER.json',
                    'docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/EXCLUSION_LISTS.json',
                    'scripts/research/discovery_sprint_04/d13_panel.py'):
        assert 'tests/research/test_gv0r01_c013_market_test.py' in _pr_gate()._select_targets([], [changed]), changed


def test_beta_suites_run_on_every_pr():
    gate = _pr_gate()
    for suite in gate.BETA_SUITES:
        assert (REPO / suite).is_dir(), suite
        assert any((REPO / suite).glob("test_*.py")), suite
    for changed in ([], ["docs/PRE_BETA_BACKLOG_V1.md"], ["beta/delivery.py"], ["runtime/beta_bot.py"],
                    ["config/beta_v0.yaml"], ["analytics/percentile_engine/compute.py"]):
        targets = gate._select_targets(gate._load_always(), changed)
        assert set(gate.BETA_SUITES) <= set(targets), changed


def test_changed_beta_test_file_is_not_selected_twice():
    gate = _pr_gate()
    targets = gate._select_targets([], ["tests/beta/test_beta_sender.py"])
    assert "tests/beta/test_beta_sender.py" not in targets
    assert targets.count("tests/beta") == 1


def test_workflows_give_the_beta_suites_their_own_database():
    for workflow in (".github/workflows/ci.yml", ".github/workflows/full-regression.yml"):
        text = (REPO / workflow).read_text(encoding="utf-8")
        assert "BETA_TEST_DSN: postgresql://postgres:postgres@localhost:5432/signalbot_beta_test" in text, workflow
        assert 'CREATE DATABASE signalbot_beta_test' in text, workflow
        for line in text.splitlines():
            if "BETA_TEST_DSN:" in line:
                assert not line.rstrip().endswith("/signalbot_test"), (workflow, line)
