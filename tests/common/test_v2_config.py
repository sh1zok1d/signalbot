"""Unit tests for common/v2_config.py (Multi-model Framework foundation PR)."""
from __future__ import annotations

import pytest

from common.v2_config import MODEL_FAMILY, V2Config, V2ConfigError, validate_rules_version


def _base_block() -> dict:
    return {"enabled": False, "model_family": "v2", "rules_version": "v2-rules-v0.1.0"}


# -- real file loads and is disabled -----------------------------------------
def test_real_file_loads_and_is_disabled():
    cfg = V2Config.load()
    assert cfg.enabled is False
    assert cfg.model_family == "v2"
    assert cfg.rules_version == "v2-rules-v0.1.0"


def test_real_file_rules_version_is_valid_shape():
    cfg = V2Config.load()
    # Round-trips through the same validator load() itself already applied —
    # exercising the public function directly, not just its internal use.
    assert validate_rules_version(cfg.rules_version) == cfg.rules_version


# -- from_mapping: valid ------------------------------------------------------
def test_from_mapping_valid():
    cfg = V2Config.from_mapping(_base_block())
    assert cfg.enabled is False
    assert cfg.model_family == MODEL_FAMILY
    assert cfg.rules_version == "v2-rules-v0.1.0"


def test_from_mapping_enabled_true_accepted():
    block = _base_block()
    block["enabled"] = True
    cfg = V2Config.from_mapping(block)
    assert cfg.enabled is True


# -- malformed enabled ---------------------------------------------------------
@pytest.mark.parametrize("bad_enabled", ["false", 0, 1, None, "true"])
def test_malformed_enabled_rejected(bad_enabled):
    block = _base_block()
    block["enabled"] = bad_enabled
    with pytest.raises(V2ConfigError, match="enabled"):
        V2Config.from_mapping(block)


# -- wrong model_family --------------------------------------------------------
@pytest.mark.parametrize("bad_family", ["v1", "V2", "v2 ", "", None, 2])
def test_wrong_model_family_rejected(bad_family):
    block = _base_block()
    block["model_family"] = bad_family
    with pytest.raises(V2ConfigError, match="model_family"):
        V2Config.from_mapping(block)


# -- malformed rules_version ----------------------------------------------------
@pytest.mark.parametrize("bad_version", [
    "",
    None,
    "forecast-rules-v0.1.0",   # V1 namespace
    "v2-rules-0.1.0",          # missing leading v
    "v2-rules-v0.1",           # missing patch
    "v2-rules-v",              # missing semantic version entirely
    "V2-RULES-V0.1.0",         # wrong case
])
def test_malformed_rules_version_rejected(bad_version):
    block = _base_block()
    block["rules_version"] = bad_version
    with pytest.raises(V2ConfigError, match="rules_version"):
        V2Config.from_mapping(block)


def test_validate_rules_version_standalone():
    assert validate_rules_version("v2-rules-v1.2.3") == "v2-rules-v1.2.3"
    with pytest.raises(V2ConfigError):
        validate_rules_version("bogus")


# -- exact-identity hardening: ASCII-only digits, full-string match only --------
# rules_version is an exact persisted historical identity string (§3): no
# trailing newline/CR/space or non-ASCII digit is ever valid, and none of
# them may be silently stripped/normalized away.
def test_validate_rules_version_rejects_trailing_newline():
    with pytest.raises(V2ConfigError, match="rules_version"):
        validate_rules_version("v2-rules-v0.1.0\n")


def test_validate_rules_version_rejects_trailing_carriage_return():
    with pytest.raises(V2ConfigError, match="rules_version"):
        validate_rules_version("v2-rules-v0.1.0\r")


def test_validate_rules_version_rejects_trailing_and_leading_space():
    with pytest.raises(V2ConfigError, match="rules_version"):
        validate_rules_version("v2-rules-v0.1.0 ")
    with pytest.raises(V2ConfigError, match="rules_version"):
        validate_rules_version(" v2-rules-v0.1.0")


@pytest.mark.parametrize("unicode_digit_version", [
    "v2-rules-v1٢.0.0",   # Arabic-Indic digit ٢ (U+0662)
    "v2-rules-v1१.0.0",   # Devanagari digit १ (U+0967)
    "v2-rules-v٠.1.0",    # Arabic-Indic zero ٠ (U+0660)
])
def test_validate_rules_version_rejects_unicode_decimal_digits(unicode_digit_version):
    # Python's \d is Unicode-aware for str patterns; the validator's regex
    # must use explicit [0-9] so a non-ASCII decimal digit can never
    # masquerade as a valid version component.
    with pytest.raises(V2ConfigError, match="rules_version"):
        validate_rules_version(unicode_digit_version)


@pytest.mark.parametrize("leading_zero_version", [
    "v2-rules-v01.0.0",   # leading zero, major
    "v2-rules-v0.01.0",   # leading zero, minor
    "v2-rules-v0.1.00",   # leading zero, patch
])
def test_validate_rules_version_rejects_leading_zeros_in_any_component(leading_zero_version):
    with pytest.raises(V2ConfigError, match="rules_version"):
        validate_rules_version(leading_zero_version)


def test_validate_rules_version_accepts_standalone_zero_component():
    # A lone "0" (not "00"/"01") is the one legal zero shape per component.
    assert validate_rules_version("v2-rules-v0.0.0") == "v2-rules-v0.0.0"


def test_validate_rules_version_never_coerces_or_strips():
    # A malformed input fails outright; it is never silently normalized
    # (e.g. stripped of whitespace) into something that would then pass.
    with pytest.raises(V2ConfigError):
        validate_rules_version("  v2-rules-v0.1.0  ")


def test_validate_rules_version_uses_fullmatch_semantics():
    # fullmatch(), never match() with a bare ^...$ pair: match() can accept
    # a trailing newline because Python's $ matches immediately before one.
    import inspect

    import common.v2_config as v2_config_module
    src = inspect.getsource(v2_config_module.validate_rules_version)
    assert "fullmatch" in src
    assert ".match(" not in src


def test_rules_version_regex_uses_ascii_digit_class_not_unicode_d():
    from common.v2_config import RULES_VERSION_RE
    assert r"\d" not in RULES_VERSION_RE.pattern
    assert "[0-9]" in RULES_VERSION_RE.pattern


# -- V2Config.from_mapping() inherits the same strict rules_version behavior ---
def test_from_mapping_rejects_rules_version_with_trailing_newline():
    block = _base_block()
    block["rules_version"] = "v2-rules-v0.1.0\n"
    with pytest.raises(V2ConfigError, match="rules_version"):
        V2Config.from_mapping(block)


def test_from_mapping_rejects_rules_version_with_unicode_digit():
    block = _base_block()
    block["rules_version"] = "v2-rules-v1٢.0.0"
    with pytest.raises(V2ConfigError, match="rules_version"):
        V2Config.from_mapping(block)


def test_from_mapping_still_accepts_valid_rules_version_after_hardening():
    # Regression guard: the hardening must not become over-strict.
    block = _base_block()
    block["rules_version"] = "v2-rules-v12.34.56"
    cfg = V2Config.from_mapping(block)
    assert cfg.rules_version == "v2-rules-v12.34.56"


# -- missing required fields ----------------------------------------------------
@pytest.mark.parametrize("missing_key", ["enabled", "model_family", "rules_version"])
def test_missing_required_key_rejected(missing_key):
    block = _base_block()
    del block[missing_key]
    with pytest.raises(V2ConfigError, match="missing required"):
        V2Config.from_mapping(block)


def test_empty_mapping_rejected():
    with pytest.raises(V2ConfigError, match="missing required"):
        V2Config.from_mapping({})


# -- unknown keys rejected (strict loader) --------------------------------------
def test_unknown_key_rejected():
    block = _base_block()
    block["rule_version"] = "typo-of-rules_version"  # plausible typo, must NOT be silently ignored
    with pytest.raises(V2ConfigError, match="unknown key"):
        V2Config.from_mapping(block)


def test_unknown_key_rejected_even_when_otherwise_valid():
    block = _base_block()
    block["extra_future_field"] = "anything"
    with pytest.raises(V2ConfigError, match="unknown key"):
        V2Config.from_mapping(block)


# -- top-level file shape ---------------------------------------------------------
def test_load_missing_v2_key_rejected(tmp_path):
    bad = tmp_path / "v2.yaml"
    bad.write_text("not_v2:\n  enabled: false\n", encoding="utf-8")
    with pytest.raises(V2ConfigError, match="v2"):
        V2Config.load(bad)


def test_load_non_mapping_top_level_rejected(tmp_path):
    bad = tmp_path / "v2.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(V2ConfigError, match="mapping"):
        V2Config.load(bad)


def test_load_v2_block_not_a_mapping_rejected(tmp_path):
    bad = tmp_path / "v2.yaml"
    bad.write_text("v2: not-a-mapping\n", encoding="utf-8")
    with pytest.raises(V2ConfigError, match="mapping"):
        V2Config.load(bad)


def test_load_unknown_sibling_top_level_key_rejected(tmp_path):
    # A plausible typo of "v2:" sitting alongside a valid v2 block must not
    # be silently ignored — config/v2.yaml is a strict identity config, only
    # "v2" is permitted at the top level.
    bad = tmp_path / "v2.yaml"
    bad.write_text(
        "v2:\n"
        "  enabled: false\n"
        "  model_family: \"v2\"\n"
        "  rules_version: \"v2-rules-v0.1.0\"\n"
        "vv2:\n"
        "  enabled: false\n",
        encoding="utf-8",
    )
    with pytest.raises(V2ConfigError, match="unknown top-level key"):
        V2Config.load(bad)


def test_load_unknown_extra_top_level_key_rejected(tmp_path):
    bad = tmp_path / "v2.yaml"
    bad.write_text(
        "v2:\n"
        "  enabled: false\n"
        "  model_family: \"v2\"\n"
        "  rules_version: \"v2-rules-v0.1.0\"\n"
        "extra:\n"
        "  anything: true\n",
        encoding="utf-8",
    )
    with pytest.raises(V2ConfigError, match="unknown top-level key"):
        V2Config.load(bad)


def test_load_only_v2_top_level_key_still_accepted(tmp_path):
    # Sanity: the real checked-in shape (only "v2:") still loads cleanly
    # after the top-level strictness hardening.
    good = tmp_path / "v2.yaml"
    good.write_text(
        "v2:\n"
        "  enabled: false\n"
        "  model_family: \"v2\"\n"
        "  rules_version: \"v2-rules-v0.1.0\"\n",
        encoding="utf-8",
    )
    cfg = V2Config.load(good)
    assert cfg.model_family == "v2"


# -- no mutation of caller's parsed state ----------------------------------------
def test_from_mapping_does_not_mutate_caller_dict():
    block = _base_block()
    original = dict(block)
    V2Config.from_mapping(block)
    assert block == original
