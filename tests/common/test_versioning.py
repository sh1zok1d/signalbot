"""Unit tests for common/versioning.py — canonical JSON + deterministic hashing."""
from __future__ import annotations

import hashlib
import json
import re

import pytest

from common import versioning as v
from common.versioning import (
    VersioningError, canonical_json, compute_calculation_version, config_hash,
    resolve_code_version,
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
