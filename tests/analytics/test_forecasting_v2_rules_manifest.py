"""Tests for analytics/forecasting_v2/rules_manifest.py (the lightweight
rules/version integrity guard). Pure module -- no DB/clock/network; the
manifest is a pure function of already-imported constants.

Exercises: `build_rules_manifest()` returns a plain JSON-serializable
dict; `compute_rules_fingerprint()` is a deterministic, key-order-stable
SHA-256 hex digest; the LIVE manifest's fingerprint matches the frozen
`EXPECTED_FINGERPRINTS_BY_RULES_VERSION["v2-rules-v0.2.0"]` anchor exactly
-- a version-participating constant mutated without a corresponding
`rules_version` bump is the exact class of bug this module exists to
catch, so this is the load-bearing regression; `assert_rules_manifest_
matches_version()` passes for the current version, raises for an
unrecognized version, and raises if the live manifest ever drifts from
the frozen anchor."""
from __future__ import annotations

import hashlib
import json

import pytest

from analytics.forecasting_v2.rules_manifest import (
    EXPECTED_FINGERPRINTS_BY_RULES_VERSION,
    V2RulesManifestError,
    assert_rules_manifest_matches_version,
    build_rules_manifest,
    compute_rules_fingerprint,
)
from common.v2_config import V2Config

CURRENT_RULES_VERSION = "v2-rules-v0.2.0"


# ============================================================================
# 1. build_rules_manifest() shape
# ============================================================================
def test_manifest_is_json_serializable():
    manifest = build_rules_manifest()
    # Must not raise -- every leaf is a bool/int/float/str.
    json.dumps(manifest)


def test_manifest_covers_every_currently_implemented_module():
    manifest = build_rules_manifest()
    assert set(manifest.keys()) == {
        "family_quality", "regime_4h", "bias_1h", "setup_common",
        "trend_pullback", "compression_breakout", "confirmed_breakout",
    }


def test_manifest_leaves_are_scalars_only():
    manifest = build_rules_manifest()
    for group_name, group in manifest.items():
        assert isinstance(group, dict), group_name
        for key, value in group.items():
            assert isinstance(value, (bool, int, float, str)), (group_name, key, type(value))


def test_manifest_is_pure_repeated_calls_identical():
    assert build_rules_manifest() == build_rules_manifest()


# ============================================================================
# 2. compute_rules_fingerprint() determinism
# ============================================================================
def test_fingerprint_is_deterministic_sha256_hex():
    manifest = build_rules_manifest()
    fp = compute_rules_fingerprint(manifest)
    assert isinstance(fp, str)
    assert len(fp) == 64
    int(fp, 16)  # must be valid hex


def test_fingerprint_matches_manual_canonical_json_sha256():
    manifest = build_rules_manifest()
    expected = hashlib.sha256(
        json.dumps(dict(manifest), sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    assert compute_rules_fingerprint(manifest) == expected


def test_fingerprint_is_key_order_independent():
    manifest = build_rules_manifest()
    reordered = dict(reversed(list(manifest.items())))
    assert compute_rules_fingerprint(manifest) == compute_rules_fingerprint(reordered)


def test_fingerprint_changes_if_any_leaf_value_changes():
    manifest = dict(build_rules_manifest())
    mutated = dict(manifest)
    group_name = next(iter(mutated))
    mutated_group = dict(mutated[group_name])
    leaf_name = next(iter(mutated_group))
    mutated_group[leaf_name] = mutated_group[leaf_name] + 999999 \
        if isinstance(mutated_group[leaf_name], (int, float)) else "mutated"
    mutated[group_name] = mutated_group
    assert compute_rules_fingerprint(mutated) != compute_rules_fingerprint(manifest)


# ============================================================================
# 3. LOAD-BEARING: the live manifest matches the frozen anchor for the
# CURRENT shipped rules_version -- this is the actual regression this
# whole module exists to catch (a constant mutated without a
# rules_version bump).
# ============================================================================
def test_live_manifest_fingerprint_matches_frozen_anchor_for_current_version():
    manifest = build_rules_manifest()
    actual = compute_rules_fingerprint(manifest)
    assert actual == EXPECTED_FINGERPRINTS_BY_RULES_VERSION[CURRENT_RULES_VERSION]


def test_assert_rules_manifest_matches_version_passes_for_current_version():
    assert_rules_manifest_matches_version(CURRENT_RULES_VERSION)  # must not raise


def test_assert_raises_for_unrecognized_version():
    with pytest.raises(V2RulesManifestError):
        assert_rules_manifest_matches_version("v2-rules-v0.999.0")


def test_assert_raises_if_live_manifest_drifts_from_frozen_anchor(monkeypatch):
    import analytics.forecasting_v2.rules_manifest as rm
    monkeypatch.setitem(
        rm.EXPECTED_FINGERPRINTS_BY_RULES_VERSION, CURRENT_RULES_VERSION, "0" * 64)
    with pytest.raises(V2RulesManifestError):
        assert_rules_manifest_matches_version(CURRENT_RULES_VERSION)


# ============================================================================
# 4. config/v2.yaml's own rules_version is exactly the CURRENT shipped
# version, and its manifest fingerprint is recorded (propagation check --
# the real deployed config, not just a literal in this test file).
# ============================================================================
def test_real_v2_yaml_rules_version_has_a_recorded_expected_fingerprint():
    config = V2Config.load()
    assert isinstance(config, V2Config)
    assert config.rules_version == CURRENT_RULES_VERSION
    assert config.rules_version in EXPECTED_FINGERPRINTS_BY_RULES_VERSION


def test_real_v2_yaml_rules_version_manifest_actually_verifies():
    config = V2Config.load()
    assert_rules_manifest_matches_version(config.rules_version)  # must not raise


# ============================================================================
# 5. explicit allow-list, never vars()/dir() introspection -- the manifest
# must not accidentally pick up a name added to a module for unrelated
# reasons (helper functions, imports, exception classes).
# ============================================================================
def test_manifest_module_does_not_use_vars_or_dir_introspection():
    import ast
    import inspect

    import analytics.forecasting_v2.rules_manifest as rm_module
    tree = ast.parse(inspect.getsource(rm_module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("vars", "dir"), (
                "rules_manifest.py must use an explicit allow-list, never "
                "vars()/dir() introspection")
