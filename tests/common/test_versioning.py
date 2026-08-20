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
    """The real (non-test) DEFAULT_FEATURE_CODE_PATHS covers exactly the
    modules analytics/feature_engine/pipeline.py and
    consensus_pipeline.py import from, confirmed by direct inspection at
    write time -- this test pins that scope so a future addition to the
    pipeline's import surface is a deliberate, reviewed change to this
    constant, never a silent gap."""
    assert v.DEFAULT_FEATURE_CODE_PATHS == (
        "analytics/feature_engine", "common/stage2_config.py", "common/versioning.py")


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
