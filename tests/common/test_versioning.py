"""Unit tests for common/versioning.py — canonical JSON + deterministic hashing."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from common import versioning as v
from common.versioning import (
    VersioningError, canonical_json, compute_calculation_version, config_hash,
    resolve_code_version, resolve_feature_code_version,
)


def _cj(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_canonical_json_deterministic_and_key_order_invariant():
    a = {"b": 1, "a": {"y": 2, "x": 1}}
    b = {"a": {"x": 1, "y": 2}, "b": 1}
    assert canonical_json(a) == canonical_json(b)
    assert canonical_json(a) == '{"a":{"x":1,"y":2},"b":1}'


def test_config_hash_deterministic_and_order_invariant():
    a = {"timeframes": ["1m", "5m"], "windows": ["7d", "30d"], "mec": 2}
    b = {"mec": 2, "windows": ["7d", "30d"], "timeframes": ["1m", "5m"]}
    assert config_hash(a) == config_hash(b)
    assert len(config_hash(a)) == 64


def test_semantic_config_change_changes_hash():
    a = {"mec": 2}
    b = {"mec": 3}
    assert config_hash(a) != config_hash(b)


def test_calculation_version_exact_formula():
    fsv, ch, code = 1, "a" * 64, "code-v1"
    expected = hashlib.sha256(
        _cj({"feature_schema_version": fsv, "config_hash": ch, "code_version": code})
        .encode("utf-8")).hexdigest()[:16]
    assert compute_calculation_version(fsv, ch, code) == expected


def test_calculation_version_length_and_lowercase_hex():
    cv = compute_calculation_version(1, "x" * 64, "code")
    assert len(cv) == 16
    assert re.fullmatch(r"[0-9a-f]{16}", cv)


def test_each_input_forks_calculation_version():
    base = compute_calculation_version(1, "h1", "c1")
    assert compute_calculation_version(2, "h1", "c1") != base   # fsv
    assert compute_calculation_version(1, "h2", "c1") != base   # config_hash
    assert compute_calculation_version(1, "h1", "c2") != base   # code_version


def test_calculation_version_rejects_empty_or_bad_inputs():
    with pytest.raises(VersioningError):
        compute_calculation_version(1, "h", "")           # empty code_version
    with pytest.raises(VersioningError):
        compute_calculation_version(1, "", "c")           # empty config_hash
    with pytest.raises(VersioningError):
        compute_calculation_version(True, "h", "c")       # bool is not a valid int
    with pytest.raises(VersioningError):
        compute_calculation_version(1, "h", "   ")        # whitespace-only 'unknown'


def test_resolve_code_version_prefers_explicit_then_env(monkeypatch):
    assert resolve_code_version("explicit-v", allow_git=False) == "explicit-v"
    monkeypatch.setenv("STAGE2_CODE_VERSION", "env-v")
    assert resolve_code_version(None, allow_git=False) == "env-v"


def test_resolve_code_version_unresolved_fails_explicitly(monkeypatch):
    monkeypatch.delenv("STAGE2_CODE_VERSION", raising=False)
    with pytest.raises(VersioningError):
        resolve_code_version(None, env_var="STAGE2_CODE_VERSION", allow_git=False)


def test_resolve_code_version_blank_env_fails(monkeypatch):
    for blank in ("", "   ", "\t"):
        monkeypatch.setenv("STAGE2_CODE_VERSION", blank)
        with pytest.raises(VersioningError):
            resolve_code_version(None, env_var="STAGE2_CODE_VERSION", allow_git=False)


def test_canonical_json_handles_mappingproxy_and_tuple():
    from types import MappingProxyType
    frozen = MappingProxyType({"b": (1, 2), "a": MappingProxyType({"x": 1})})
    plain = {"a": {"x": 1}, "b": [1, 2]}
    # frozen (mappingproxy + tuple) hashes/serializes identically to plain
    assert canonical_json(frozen) == canonical_json(plain)
    assert canonical_json(frozen) == '{"a":{"x":1},"b":[1,2]}'


def test_canonical_json_rejects_nonfinite_and_unsupported():
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
    with pytest.raises(ValueError):
        canonical_json({"x": float("inf")})
    with pytest.raises(TypeError):
        canonical_json({"x": object()})


# ============================================================================
# resolve_feature_code_version — path-scoped feature-computation code
# identity (V2-H2a, §3.3a). Uses a real, isolated, throwaway git repo (never
# the actual signalbot repo, whose live dirty state is not test-controlled)
# so every assertion is fully hermetic and deterministic.
# ============================================================================
def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def scoped_repo(tmp_path) -> Path:
    """A throwaway git repo with an `in_scope/` dir, an `out_of_scope/`
    dir, and one initial commit touching both."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "in_scope").mkdir()
    (repo / "in_scope" / "a.py").write_text("A = 1\n")
    (repo / "out_of_scope").mkdir()
    (repo / "out_of_scope" / "b.py").write_text("B = 1\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "initial"], repo)
    return repo


def _head(repo: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def test_feature_version_prefers_explicit_then_env(scoped_repo, monkeypatch):
    assert resolve_feature_code_version(
        "explicit-v", paths=("in_scope",), repo_root=scoped_repo, allow_git=False) == "explicit-v"
    monkeypatch.setenv("STAGE2_CODE_VERSION", "env-v")
    assert resolve_feature_code_version(
        None, paths=("in_scope",), repo_root=scoped_repo, allow_git=False) == "env-v"


def test_feature_version_clean_repo_returns_commit_hash(scoped_repo):
    result = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert result == _head(scoped_repo)
    assert re.fullmatch(r"[0-9a-f]{40}", result)


def test_feature_version_deterministic_across_calls(scoped_repo):
    a = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    b = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert a == b


def test_feature_version_insensitive_to_out_of_scope_dirty_change(scoped_repo):
    """The core §3.3a isolation proof: a working-tree edit OUTSIDE `paths`
    must not change the resolved value at all -- not even a `-dirty`
    suffix."""
    baseline = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    (scoped_repo / "out_of_scope" / "b.py").write_text("B = 2  # unrelated edit\n")
    after = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert after == baseline


def test_feature_version_insensitive_to_out_of_scope_new_commit(scoped_repo):
    baseline = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    (scoped_repo / "out_of_scope" / "c.py").write_text("C = 1\n")
    _git(["add", "-A"], scoped_repo)
    _git(["commit", "-q", "-m", "unrelated change"], scoped_repo)
    after = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert after == baseline


def test_feature_version_sensitive_to_in_scope_dirty_change(scoped_repo):
    baseline = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    (scoped_repo / "in_scope" / "a.py").write_text("A = 2  # relevant edit\n")
    after = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert after != baseline
    assert after.startswith(baseline + "-dirty-") or "-dirty-" in after


def test_feature_version_sensitive_to_in_scope_new_commit(scoped_repo):
    baseline = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    (scoped_repo / "in_scope" / "d.py").write_text("D = 1\n")
    _git(["add", "-A"], scoped_repo)
    _git(["commit", "-q", "-m", "relevant change"], scoped_repo)
    after = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert after != baseline
    assert after == _head(scoped_repo)


def test_feature_version_dirty_suffix_is_content_deterministic(scoped_repo):
    """Same dirty content -> same suffix, reproduced across two independent
    resolutions -- never a timestamp or anything nondeterministic."""
    (scoped_repo / "in_scope" / "a.py").write_text("A = 2\n")
    first = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    second = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert first == second


def test_feature_version_untracked_in_scope_file_counts_as_dirty(scoped_repo):
    baseline = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    (scoped_repo / "in_scope" / "untracked.py").write_text("U = 1\n")
    after = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert after != baseline
    assert "-dirty-" in after


def test_feature_version_staged_in_scope_file_counts_as_dirty(scoped_repo):
    baseline = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    (scoped_repo / "in_scope" / "staged.py").write_text("S = 1\n")
    _git(["add", "in_scope/staged.py"], scoped_repo)
    after = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
    assert after != baseline
    assert "-dirty-" in after


def test_feature_version_no_commit_and_not_dirty_raises(tmp_path):
    repo = tmp_path / "empty_repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "unrelated.py").write_text("X = 1\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "unrelated only"], repo)
    with pytest.raises(VersioningError):
        resolve_feature_code_version(paths=("never_existed",), repo_root=repo)


def test_feature_version_allow_git_false_without_explicit_or_env_raises(
        scoped_repo, monkeypatch):
    monkeypatch.delenv("STAGE2_CODE_VERSION", raising=False)
    with pytest.raises(VersioningError):
        resolve_feature_code_version(
            None, paths=("in_scope",), repo_root=scoped_repo, allow_git=False)


def test_feature_version_empty_paths_raises(scoped_repo):
    with pytest.raises(VersioningError, match="paths"):
        resolve_feature_code_version(paths=(), repo_root=scoped_repo)


def test_feature_version_blank_env_falls_through_to_git(scoped_repo, monkeypatch):
    for blank in ("", "   ", "\t"):
        monkeypatch.setenv("STAGE2_CODE_VERSION", blank)
        result = resolve_feature_code_version(paths=("in_scope",), repo_root=scoped_repo)
        assert result == _head(scoped_repo)


def test_feature_version_never_falls_back_to_whole_repo_describe():
    """resolve_feature_code_version never invokes the `git describe`
    subcommand -- confirmed by source inspection of the actual git
    argument list, not just behavior, so a future edit can't quietly
    reintroduce the whole-repo fallback this function exists to replace."""
    import inspect
    src = inspect.getsource(v.resolve_feature_code_version)
    assert '"describe"' not in src
    assert "'describe'" not in src


def test_default_feature_code_paths_matches_real_pipeline_surface():
    """The real (non-test) DEFAULT_FEATURE_CODE_PATHS covers the FULL
    transitive import closure of `analytics/feature_engine/` and
    `analytics/percentile_engine/` -- confirmed by direct inspection of
    every `from`/`import` line in both packages at write time (Qodo
    amendment round 1, finding 2: the first version omitted
    `analytics/percentile_engine/` and several direct feature-engine
    dependencies -- `common/instrument_metadata.py`, `symbols/registry.py`
    -- even though both packages import them and their outputs
    demonstrably depend on them). This test pins that scope so a future
    addition to either package's import surface is a deliberate, reviewed
    change to this constant, never a silent gap."""
    assert v.DEFAULT_FEATURE_CODE_PATHS == (
        "analytics/feature_engine",
        "analytics/percentile_engine",
        "common/stage2_config.py",
        "common/versioning.py",
        "common/instrument_metadata.py",
        "common/symbol_mapper.py",
        "symbols/registry.py",
        "common/capabilities.py",
    )


def test_default_feature_code_paths_covers_every_direct_import_of_both_packages():
    """Re-derive the transitive closure from the REAL source files (never
    trusting a hand-maintained list to stay in sync with itself) and
    assert it is a SUBSET of `DEFAULT_FEATURE_CODE_PATHS` -- catches the
    exact class of gap Qodo amendment round 1's finding 2 found: a
    package importing a module this constant does not list."""
    import ast

    repo_root = Path(__file__).resolve().parent.parent.parent
    package_dirs = [repo_root / "analytics" / "feature_engine",
                     repo_root / "analytics" / "percentile_engine"]
    scoped_prefixes = {"analytics", "common", "symbols"}
    discovered: set = set()

    def _module_to_relpath(module: str) -> "str | None":
        # Only resolve modules under our own scoped top-level packages
        # (never a stdlib/third-party import) -- e.g. "common.versioning"
        # -> "common/versioning.py".
        top = module.split(".")[0]
        if top not in scoped_prefixes:
            return None
        candidate = repo_root / (module.replace(".", "/") + ".py")
        if candidate.is_file():
            return str(candidate.relative_to(repo_root))
        return None

    for pkg_dir in package_dirs:
        for py_file in pkg_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    rel = _module_to_relpath(node.module)
                    if rel is not None:
                        discovered.add(rel)

    # Every discovered direct dependency must be covered by
    # DEFAULT_FEATURE_CODE_PATHS -- either the exact file, or a package
    # directory prefix that contains it.
    for rel in discovered:
        covered = any(
            rel == scoped or rel.startswith(scoped.rstrip("/") + "/")
            for scoped in v.DEFAULT_FEATURE_CODE_PATHS)
        assert covered, (
            f"{rel!r} is imported directly by analytics/feature_engine or "
            f"analytics/percentile_engine but is not covered by "
            f"DEFAULT_FEATURE_CODE_PATHS={v.DEFAULT_FEATURE_CODE_PATHS!r}")


# ============================================================================
# Full-scope hermetic proof (Qodo amendment round 1, finding 2): using the
# REAL (unmodified) `DEFAULT_FEATURE_CODE_PATHS` against a throwaway repo
# whose tree mirrors every one of those real relative paths, prove that
# changing ANY in-scope component forks the resolved identity, while an
# unrelated docs/Stage-6/Telegram-analog change does not.
# ============================================================================
_DEFAULT_SCOPE_FILES = {
    "analytics/feature_engine/__init__.py": "FEATURE_ENGINE = 1\n",
    "analytics/feature_engine/units.py": "UNITS = 1\n",
    "analytics/percentile_engine/__init__.py": "PERCENTILE_ENGINE = 1\n",
    "analytics/percentile_engine/compute.py": "COMPUTE = 1\n",
    "common/stage2_config.py": "STAGE2_CONFIG = 1\n",
    "common/versioning.py": "VERSIONING = 1\n",
    "common/instrument_metadata.py": "INSTRUMENT_METADATA = 1\n",
    "common/symbol_mapper.py": "SYMBOL_MAPPER = 1\n",
    "symbols/registry.py": "REGISTRY = 1\n",
    "common/capabilities.py": "CAPABILITIES = 1\n",
}
_OUT_OF_SCOPE_FILES = {
    "docs/SOME_DOC.md": "# an unrelated docs-only change\n",
    "analytics/forecasting_v2/some_stage6_module.py": "STAGE6_STAND_IN = 1\n",
    "notifications/telegram_client.py": "TELEGRAM_STAND_IN = 1\n",
}


def _init_default_scope_repo(tmp_path):
    """A throwaway git repo whose tree mirrors every REAL relative path in
    `common.versioning.DEFAULT_FEATURE_CODE_PATHS`, plus three unrelated
    stand-ins (a docs file, a Stage-6-analog V2 module, a Telegram-analog
    module) -- one initial commit touching everything."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    for rel_path, content in {**_DEFAULT_SCOPE_FILES, **_OUT_OF_SCOPE_FILES}.items():
        target = repo / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "initial"], repo)
    return repo


@pytest.mark.parametrize("rel_path", sorted(_DEFAULT_SCOPE_FILES))
def test_default_scope_in_scope_component_forks_identity(rel_path, tmp_path):
    """Changing ANY of the 8 real `DEFAULT_FEATURE_CODE_PATHS` components
    -- including the two `analytics/percentile_engine/` files and the four
    direct feature-engine dependencies Qodo's finding 2 originally found
    missing -- must fork the resolved feature code identity."""
    repo = _init_default_scope_repo(tmp_path)
    baseline = resolve_feature_code_version(paths=v.DEFAULT_FEATURE_CODE_PATHS, repo_root=repo)
    (repo / rel_path).write_text("changed = True\n")
    after = resolve_feature_code_version(paths=v.DEFAULT_FEATURE_CODE_PATHS, repo_root=repo)
    assert after != baseline, f"changing {rel_path!r} must fork feature code identity"


@pytest.mark.parametrize("rel_path", sorted(_OUT_OF_SCOPE_FILES))
def test_default_scope_unrelated_component_does_not_fork_identity(rel_path, tmp_path):
    """A docs-only change, a Stage-6-analog V2 module change, and a
    Telegram-analog module change must NOT fork the resolved feature code
    identity -- the exact §3.3a isolation guarantee, proven against the
    REAL default scope, not a synthetic override."""
    repo = _init_default_scope_repo(tmp_path)
    baseline = resolve_feature_code_version(paths=v.DEFAULT_FEATURE_CODE_PATHS, repo_root=repo)
    (repo / rel_path).write_text("changed = True\n")
    after = resolve_feature_code_version(paths=v.DEFAULT_FEATURE_CODE_PATHS, repo_root=repo)
    assert after == baseline, f"changing unrelated {rel_path!r} must NOT fork feature code identity"


def test_stage2_isolation_regression_still_uses_pure_compute_calculation_version():
    """Belt-and-suspenders: tests/common/test_v2_stage2_isolation.py's
    load-bearing isolation proof calls compute_calculation_version()
    directly with an explicit code_version, never resolve_code_version()
    or resolve_feature_code_version() -- so this PR's new resolver cannot
    have silently weakened that regression's own hermeticity."""
    with open(
        Path(__file__).resolve().parent / "test_v2_stage2_isolation.py", encoding="utf-8"
    ) as f:
        src = f.read()
    assert "resolve_code_version" not in src
    assert "resolve_feature_code_version" not in src
    assert '_CODE_VERSION = "test-code-version-v0"' in src
