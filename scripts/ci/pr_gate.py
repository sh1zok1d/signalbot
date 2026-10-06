#!/usr/bin/env python3
"""Fast PR gate for pull_request → main.

FAST PR GATE (this file) is required for ordinary PR iteration.
FULL REGRESSION is `python -m pytest -q` via
`.github/workflows/full-regression.yml` (workflow_dispatch and push to main).

Does not mint RESULT, consume reservations, or rerun MARKET-01.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PATHS_FILE = Path(__file__).with_name("pr_gate_paths.txt")

# Whole-module suites that dominate the old 1h42m research tail. They stay
# in FULL REGRESSION. The gate still runs named nodeids from these files
# when listed in pr_gate_paths.txt. The whole file is added only when the
# matching source module is in the PR diff.
HEAVY_TEST_TO_SOURCE = {
    "tests/research/test_harness_synthetic_edge_calibration_v1_production.py": (
        "scripts/research/harness_synthetic_edge_calibration_v1_production.py",
    ),
    "tests/research/test_harness_synthetic_edge_calibration_v1_checkpoint_forgery.py": (
        "scripts/research/harness_synthetic_edge_calibration_v1.py",
        "scripts/research/harness_synthetic_edge_calibration_v1_auth.py",
    ),
    "tests/research/test_harness_synthetic_edge_calibration_v1_verifier_parallel.py": (
        "scripts/research/harness_synthetic_edge_calibration_v1_auth.py",
        "scripts/research/harness_synthetic_edge_calibration_v1_worker.py",
    ),
    "tests/research/test_harness_synthetic_edge_calibration_v2_production.py": (
        "scripts/research/harness_synthetic_edge_calibration_v2_production.py",
    ),
    "tests/research/test_harness_synthetic_edge_calibration_v2_production_lifecycle.py": (
        "scripts/research/harness_synthetic_edge_calibration_v2_production.py",
    ),
    "tests/research/test_core_btc_binance_v0_materializer.py": (
        "scripts/research/core_btc_binance_v0_materializer.py",
    ),
    "tests/research/test_b2_06_oi_funding_materialization.py": (
        "scripts/research/b2_06_oi_funding_materialization.py",
    ),
}


# The beta product suite runs on every PR (docs/PRE_BETA_BACKLOG_V1.md X6).
# beta/, runtime/, config/ and deploy/ have no flat source -> test mapping, and
# the beta also depends on shared analytics/ and storage/ modules, so no path
# trigger would be complete. Its PostgreSQL tests need BETA_TEST_DSN, a
# database of its own: tests/beta/beta_fakes.py::fresh_pool drops and
# recreates its public schema (see .github/workflows/ci.yml). The user
# simulator harness keeps its own suite outside this gate.
BETA_SUITES = ("tests/beta",)


def _in_beta_suite(path: str) -> bool:
    return any(path.startswith(f"{suite}/") for suite in BETA_SUITES)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def _load_always() -> list[str]:
    out: list[str] = []
    for raw in PATHS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    if not out:
        raise SystemExit(f"empty PR gate path list: {PATHS_FILE}")
    return out


def _diff_base() -> str:
    explicit = os.environ.get("PR_GATE_BASE", "").strip()
    if explicit:
        return explicit
    sha = os.environ.get("GITHUB_BASE_SHA", "").strip()
    if sha:
        return sha
    try:
        _git("rev-parse", "--verify", "origin/main")
        return "origin/main"
    except subprocess.CalledProcessError:
        return "HEAD"


def _changed_files(base: str) -> list[str]:
    try:
        text = _git("diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD")
    except subprocess.CalledProcessError:
        return []
    return [line for line in text.splitlines() if line]


def _mapped_test_for_source(path: str) -> str | None:
    p = Path(path)
    if p.suffix != ".py" or path.startswith("tests/"):
        return None
    parts = p.parts
    if len(parts) >= 2 and parts[0] in {"scripts", "analytics", "storage"}:
        if parts[0] == "scripts" and len(parts) >= 3:
            candidate = REPO / "tests" / parts[1] / f"test_{p.stem}.py"
        else:
            candidate = REPO / "tests" / parts[0] / f"test_{p.stem}.py"
        if candidate.is_file():
            return str(candidate.relative_to(REPO))
    return None


def _is_test_file(path: str) -> bool:
    if not path.startswith("tests/") or not path.endswith(".py"):
        return False
    name = Path(path).name
    return name.startswith("test_") or "/test_" in path


def _select_targets(always: list[str], changed: list[str]) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        if item not in seen:
            seen.add(item)
            selected.append(item)

    for item in always:
        add(item)
    for suite in BETA_SUITES:
        add(suite)

    # The nested Generator V0 package has multiple shared contracts; a source-only
    # change must not evade its focused suite through the flat filename mapper.
    generator_authorities = {
        'docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.json',
        'docs/research/MECHANISM_MEMORY_V0.json',
        'docs/research/HETEROGENEOUS_FAMILY_ROTATION_V3.json',
        'docs/research/BLIND_MECHANISM_MAP_V0.json',
        'docs/research/GOVERNANCE_REGION_AUTHORITY_V0.json',
        'docs/research/GENERATOR_V0_CONTEXT_PINS.json',
    }
    if any(path.startswith(('scripts/research/generator_v0/', 'docs/research/generator_v0_memory/')) or path in generator_authorities
           for path in changed):
        for test in sorted((REPO / 'tests/research').glob('test_generator_v0_*.py')):
            add(str(test.relative_to(REPO)))

    # The frozen GV0R01-C013 market test binds its prereg, test ledger, library
    # and dataset identity by digest; any of them changing must run its suite.
    c013_bound = ('scripts/research/gv0r01_c013_', 'docs/research/GV0R01_C013_',
                  'docs/research/SCIENTIFIC_TEST_LEDGER.json',
                  'docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/',
                  'scripts/research/discovery_sprint_04/')
    if any(path.startswith(c013_bound) for path in changed):
        add('tests/research/test_gv0r01_c013_market_test.py')

    changed_set = set(changed)
    changed_tests = [p for p in changed if _is_test_file(p)]
    changed_sources = [
        p for p in changed if p.endswith(".py") and not p.startswith("tests/")
    ]
    # Integration PRs vs main can touch the entire V1/V2/V3/MARKET stack.
    # Keep those on the explicit current-invariant list; auto-include the
    # extra files only for ordinary bounded diffs.
    include_changed_tests = len(changed_tests) <= 20
    include_heavy = len(changed_sources) <= 12
    if not include_changed_tests:
        print(
            f"PR_GATE skipping bulk test-file auto-include "
            f"({len(changed_tests)} test files vs base); "
            "using always-list + source-mapped tests",
            flush=True,
        )
    if not include_heavy:
        print(
            f"PR_GATE skipping heavy whole-module suites "
            f"({len(changed_sources)} source files vs base); "
            "those remain in FULL REGRESSION",
            flush=True,
        )

    heavy_triggered = set()
    if include_heavy:
        heavy_triggered = {
            test
            for test, sources in HEAVY_TEST_TO_SOURCE.items()
            if any(src in changed_set for src in sources)
        }
        for test in heavy_triggered:
            add(test)

    for path in changed:
        if not path.startswith("tests/") or not path.endswith(".py"):
            mapped = _mapped_test_for_source(path)
            if mapped is not None:
                if mapped in HEAVY_TEST_TO_SOURCE and mapped not in heavy_triggered:
                    continue
                add(mapped)
            continue
        if not include_changed_tests:
            continue
        if not _is_test_file(path):
            continue
        if _in_beta_suite(path):
            continue
        if path in HEAVY_TEST_TO_SOURCE and path not in heavy_triggered:
            continue
        add(path)
    return selected


def _compileall() -> None:
    print("PR_GATE compileall", flush=True)
    subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(REPO)],
        check=True,
    )


def _pytest(targets: list[str]) -> None:
    print("PR_GATE pytest targets:", flush=True)
    for t in targets:
        print(f"  {t}", flush=True)
    cmd = [sys.executable, "-m", "pytest", "-q", *targets]
    subprocess.run(cmd, check=True, cwd=str(REPO))


def main() -> int:
    always = _load_always()
    base = _diff_base()
    changed = _changed_files(base)
    targets = _select_targets(always, changed)
    print(f"PR_GATE base={base} changed_files={len(changed)} targets={len(targets)}", flush=True)
    _compileall()
    _pytest(targets)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode or 1) from exc
