"""Unit tests for analytics/forecasting_v2/identity.py (Multi-model Framework
foundation PR). Pure value-object tests only — no DB, network, clock, or
filesystem, matching the module's own purity guarantee."""
from __future__ import annotations

import dataclasses

import pytest

from analytics.forecasting_v2 import MODEL_FAMILY, V2IdentityError, V2ModelIdentity


def test_model_family_constant_is_v2():
    assert MODEL_FAMILY == "v2"


def test_valid_identity_accepted():
    identity = V2ModelIdentity(model_family="v2", rules_version="v2-rules-v0.1.0")
    assert identity.model_family == "v2"
    assert identity.rules_version == "v2-rules-v0.1.0"


@pytest.mark.parametrize("rules_version", [
    "v2-rules-v0.1.0",
    "v2-rules-v1.0.0",
    "v2-rules-v12.34.56",
    "v2-rules-v0.0.0",
])
def test_valid_rules_version_shapes_accepted(rules_version):
    identity = V2ModelIdentity(model_family="v2", rules_version=rules_version)
    assert identity.rules_version == rules_version


def test_wrong_model_family_rejected():
    with pytest.raises(V2IdentityError, match="model_family"):
        V2ModelIdentity(model_family="v1", rules_version="v2-rules-v0.1.0")


def test_v1_style_rule_version_rejected_as_v2_rules_version():
    # V1's own rule_version namespace (analytics/forecasting/models.py:
    # rule_version="forecast-rules-v0.1.0") must never validate as a V2
    # rules_version — the two namespaces are disjoint by construction.
    with pytest.raises(V2IdentityError, match="rules_version"):
        V2ModelIdentity(model_family="v2", rules_version="forecast-rules-v0.1.0")


def test_malformed_prefix_rejected():
    with pytest.raises(V2IdentityError, match="rules_version"):
        V2ModelIdentity(model_family="v2", rules_version="v2-rules-0.1.0")


@pytest.mark.parametrize("rules_version", [
    "v2-rules-v0.1",       # missing patch
    "v2-rules-v0",         # missing minor+patch
    "v2-rules-v",          # missing entire semantic version
    "v2-rules-v0.1.0.0",   # extra component
    "v2-rules-va.b.c",     # non-numeric
])
def test_missing_or_malformed_semantic_version_rejected(rules_version):
    with pytest.raises(V2IdentityError, match="rules_version"):
        V2ModelIdentity(model_family="v2", rules_version=rules_version)


def test_empty_rules_version_rejected():
    with pytest.raises(V2IdentityError, match="rules_version"):
        V2ModelIdentity(model_family="v2", rules_version="")


def test_non_string_rules_version_rejected():
    with pytest.raises(V2IdentityError):
        V2ModelIdentity(model_family="v2", rules_version=None)  # type: ignore[arg-type]


def test_identity_is_frozen_dataclass_immutable():
    identity = V2ModelIdentity(model_family="v2", rules_version="v2-rules-v0.1.0")
    assert dataclasses.is_dataclass(identity)
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.model_family = "v1"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.rules_version = "v2-rules-v0.2.0"  # type: ignore[misc]


def test_identity_equality_by_value():
    a = V2ModelIdentity(model_family="v2", rules_version="v2-rules-v0.1.0")
    b = V2ModelIdentity(model_family="v2", rules_version="v2-rules-v0.1.0")
    c = V2ModelIdentity(model_family="v2", rules_version="v2-rules-v0.2.0")
    assert a == b
    assert a != c


# -- rules_version exact-identity hardening propagation (common.v2_config) -----
# V2ModelIdentity must reuse common.v2_config.validate_rules_version's exact
# semantics unchanged, never its own looser/competing check.
def test_trailing_newline_rules_version_rejected():
    with pytest.raises(V2IdentityError, match="rules_version"):
        V2ModelIdentity(model_family="v2", rules_version="v2-rules-v0.1.0\n")


def test_unicode_decimal_digit_rules_version_rejected():
    with pytest.raises(V2IdentityError, match="rules_version"):
        V2ModelIdentity(model_family="v2", rules_version="v2-rules-v1٢.0.0")


def test_identity_module_reuses_shared_validator_not_a_second_regex():
    import inspect

    import analytics.forecasting_v2.identity as identity_module
    src = inspect.getsource(identity_module)
    assert "validate_rules_version" in src
    assert "re.compile" not in src
