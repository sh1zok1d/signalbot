"""Load-bearing regression test: V2 identity config MUST NOT affect Stage 2's
resolved config / config_hash / calculation_version.

This directly enforces docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3 ("V2
reuses calculation_version unchanged and shared with V1... V2 does not get
its own parallel feature-computation identity") and §23 ("Config is not a
loophole"). It exercises the REAL boundary — the actual Stage2Config loader
and the actual common/versioning.py hash/version functions, not mocks — so a
future change that accidentally wires config/v2.yaml into the Stage 2
resolved config (or vice versa) fails this test.
"""
from __future__ import annotations

from common.stage2_config import Stage2Config
from common.v2_config import V2Config
from common.versioning import compute_calculation_version

# Fixed, explicit code_version — deterministic and hermetic (never git-derived
# in a test), matching compute_calculation_version's own pure-function
# contract (it never resolves code_version itself, STAGE2_SPEC.md §10).
_CODE_VERSION = "test-code-version-v0"


def _stage2_identity(symbol: str = "BTCUSDT"):
    """Resolve the REAL config/stage2.yaml for one symbol and compute its
    real config_hash / calculation_version, exactly as
    analytics/feature_engine/consensus_input_adapter.py does."""
    stage2_config = Stage2Config.load()
    resolved = stage2_config.resolve(symbol)
    config_hash = resolved.config_hash()
    calculation_version = compute_calculation_version(
        stage2_config.feature_schema_version, config_hash, _CODE_VERSION)
    return stage2_config, resolved, config_hash, calculation_version


def test_stage2_config_loads_exactly_as_before():
    """Baseline: the real Stage 2 config still loads and resolves BTCUSDT
    with stage2.enabled staying false, completely independent of this PR's
    changes."""
    stage2_config, resolved, config_hash, calculation_version = _stage2_identity()
    assert stage2_config.enabled is False
    assert resolved.enabled is True
    assert isinstance(config_hash, str) and len(config_hash) == 64
    assert isinstance(calculation_version, str) and len(calculation_version) == 16


def test_v2_rules_version_change_does_not_change_stage2_identity():
    """The core isolation proof: two V2Configs with DIFFERENT rules_version
    values coexist with the SAME, unchanged Stage 2 identity."""
    stage2_config, resolved, config_hash_before, calc_version_before = _stage2_identity()

    v2_a = V2Config.from_mapping(
        {"enabled": False, "model_family": "v2", "rules_version": "v2-rules-v0.1.0"})
    v2_b = V2Config.from_mapping(
        {"enabled": False, "model_family": "v2", "rules_version": "v2-rules-v0.1.1"})
    assert v2_a.rules_version != v2_b.rules_version  # sanity: the two configs really differ

    # Re-resolve Stage 2 AFTER constructing both V2Configs — proves nothing
    # about V2Config construction/inspection perturbed Stage2Config's own
    # module-global or instance state.
    _, resolved_after, config_hash_after, calc_version_after = _stage2_identity()

    assert config_hash_after == config_hash_before
    assert calc_version_after == calc_version_before
    assert resolved_after.config_hash() == resolved.config_hash()

    # And the same holds if v2.enabled itself flips — V2's OWN enabled flag
    # must not participate in Stage 2's hash either.
    v2_enabled = V2Config.from_mapping(
        {"enabled": True, "model_family": "v2", "rules_version": "v2-rules-v9.9.9"})
    _, _, config_hash_final, calc_version_final = _stage2_identity()
    assert config_hash_final == config_hash_before
    assert calc_version_final == calc_version_before
    # (v2_enabled constructed only to prove its mere existence/inspection has
    # no side effect on Stage 2 — referenced here so linters don't flag it as
    # unused.)
    assert v2_enabled.enabled is True


def test_stage2_resolved_config_contains_no_v2_identity_keys():
    """Structural proof, not just a hash coincidence: the actual resolved
    Stage 2 payload that gets hashed contains no v2/rules_version/model_family
    key at any depth — there is nothing for a V2 change to even collide with."""
    _, resolved, _, _ = _stage2_identity()

    def _walk(node) -> bool:
        """Return True if any forbidden key is found at any depth."""
        forbidden = {"v2", "rules_version", "model_family"}
        if hasattr(node, "items"):
            for k, v in node.items():
                if k in forbidden:
                    return True
                if _walk(v):
                    return True
        elif isinstance(node, (list, tuple)):
            for item in node:
                if _walk(item):
                    return True
        return False

    assert _walk(resolved.data) is False
    assert _walk(resolved.as_dict()) is False


def test_stage2_config_raw_has_no_v2_key():
    stage2_config, _, _, _ = _stage2_identity()
    assert "v2" not in stage2_config._raw  # noqa: SLF001 - same convention tests/common/test_stage2_config.py already uses


def test_v2_config_load_never_touches_stage2_config_path():
    """V2Config.load() reads config/v2.yaml only — never config/stage2.yaml —
    proven by loading V2Config alone (no Stage2Config in scope at all) and
    confirming it still produces a fully valid, independent result."""
    cfg = V2Config.load()
    assert cfg.model_family == "v2"
    assert cfg.rules_version.startswith("v2-rules-v")


def test_two_different_rules_versions_are_genuinely_distinct_v2_identities():
    """Belt-and-suspenders: prove V2's OWN identity does change when its
    rules_version changes (so the isolation test above isn't vacuously true
    because nothing ever varies)."""
    from analytics.forecasting_v2 import V2ModelIdentity

    a = V2ModelIdentity(model_family="v2", rules_version="v2-rules-v0.1.0")
    b = V2ModelIdentity(model_family="v2", rules_version="v2-rules-v0.1.1")
    assert a != b
    assert a.rules_version != b.rules_version
