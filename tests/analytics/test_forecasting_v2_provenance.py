"""Tests for analytics/forecasting_v2/provenance.py's V2EventProvenance.

Mirrors tests/analytics/test_forecasting_v2_events.py's style for the
overlapping field validations (run_kind, model_family, rules_version,
symbol, market_type, feature_schema_version, calculation_version,
config_hash, config_version, code_version) — V2EventProvenance shares the
exact same field-shape rules via analytics/forecasting_v2/_validation.py,
never a second competing implementation.
"""
from __future__ import annotations

import dataclasses
import inspect
import textwrap

import pytest

from analytics.forecasting_v2._validation import (
    validate_calculation_version, validate_config_hash,
    validate_feature_schema_version, validate_market_type, validate_symbol,
)
from analytics.forecasting_v2.events import LIVE, REPLAY
from analytics.forecasting_v2.provenance import V2EventProvenance, V2ProvenanceError
from common.v2_config import MODEL_FAMILY, validate_rules_version

H64 = "a" * 64
H16 = "b" * 16


def make_provenance(**over) -> V2EventProvenance:
    base = dict(
        run_kind=LIVE, run_id="live-shadow",
        model_family="v2", rules_version="v2-rules-v0.1.0",
        symbol="BTCUSDT", market_type="perp",
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="deadbeef",
    )
    base.update(over)
    return V2EventProvenance(**base)


# ---- basic construction -----------------------------------------------------
def test_valid_construction():
    p = make_provenance()
    assert p.run_kind == LIVE
    assert p.model_family == "v2"
    assert p.rules_version == "v2-rules-v0.1.0"
    assert p.symbol == "BTCUSDT"
    assert p.market_type == "perp"
    assert p.feature_schema_version == 1
    assert p.calculation_version == H16
    assert p.config_hash == H64
    assert p.config_version == "2.1.0"
    assert p.code_version == "deadbeef"


def test_is_frozen_dataclass():
    p = make_provenance()
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.run_id = "other"  # type: ignore[misc]


def test_determinism_same_inputs_equal_objects():
    assert make_provenance() == make_provenance()


# ---- run_kind / run_id ------------------------------------------------------
def test_live_accepted():
    assert make_provenance(run_kind=LIVE).run_kind == LIVE


def test_replay_accepted():
    assert make_provenance(run_kind=REPLAY).run_kind == REPLAY


@pytest.mark.parametrize("bad", ["BOTH", "live", "replay", "", "LIVE_REPLAY"])
def test_third_run_kind_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="run_kind"):
        make_provenance(run_kind=bad)


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_blank_run_id_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="run_id"):
        make_provenance(run_id=bad)


def test_run_id_preserved_exactly():
    assert make_provenance(run_id="replay-001").run_id == "replay-001"


# ---- model_family / rules_version -------------------------------------------
def test_model_family_exactly_v2():
    assert make_provenance().model_family == MODEL_FAMILY == "v2"


@pytest.mark.parametrize("bad", ["v1", "V2", "2", "", None])
def test_v1_or_malformed_model_family_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="model_family"):
        make_provenance(model_family=bad)


@pytest.mark.parametrize("good", [
    "v2-rules-v0.1.0", "v2-rules-v1.0.0", "v2-rules-v10.20.30", "v2-rules-v0.0.0",
])
def test_valid_v2_rules_version_accepted(good):
    assert make_provenance(rules_version=good).rules_version == good


@pytest.mark.parametrize("bad", [
    "forecast-rules-v0.1.0",  # V1 namespace
    "v2-rules-v01.0.0",       # leading zero
    "v2-rules-v1.0",          # missing patch
    "v2-rules-0.1.0",         # missing leading v
    "",
])
def test_v1_or_malformed_rules_version_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="rules_version"):
        make_provenance(rules_version=bad)


def test_rules_version_reuses_shared_validator_not_a_second_regex():
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.provenance", fromlist=["provenance"]))
    assert "validate_rules_version" in src
    assert "re.compile" not in src   # no locally-defined competing regex
    # confirm it is literally the same function object as common.v2_config's
    from analytics.forecasting_v2 import provenance as _prov_mod
    assert _prov_mod.validate_rules_version is validate_rules_version


# -- rules_version exact-identity hardening propagation (common.v2_config) -----
def test_trailing_newline_rules_version_rejected():
    with pytest.raises(V2ProvenanceError, match="rules_version"):
        make_provenance(rules_version="v2-rules-v0.1.0\n")


def test_unicode_decimal_digit_rules_version_rejected():
    with pytest.raises(V2ProvenanceError, match="rules_version"):
        make_provenance(rules_version="v2-rules-v1٢.0.0")


# ---- symbol / market_type ----------------------------------------------------
def test_btcusdt_accepted():
    assert make_provenance(symbol="BTCUSDT").symbol == "BTCUSDT"


@pytest.mark.parametrize("bad", ["ETHUSDT", "btcusdt", "", "BTCUSD"])
def test_unsupported_symbol_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="symbol"):
        make_provenance(symbol=bad)


def test_perp_accepted():
    assert make_provenance(market_type="perp").market_type == "perp"


@pytest.mark.parametrize("bad", ["spot", "futures", "PERP", ""])
def test_spot_or_malformed_market_type_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="market_type"):
        make_provenance(market_type=bad)


def test_scope_validators_shared_with_events_module():
    # Same functions events.py itself calls — not a re-implementation.
    import analytics.forecasting_v2.events as events_mod
    src = inspect.getsource(events_mod)
    assert "validate_symbol" in src and "validate_market_type" in src


# ---- feature_schema_version --------------------------------------------------
def test_feature_schema_version_positive_int_accepted():
    assert make_provenance(feature_schema_version=3).feature_schema_version == 3


@pytest.mark.parametrize("bad", [0, -1, 1.5, "1", None])
def test_feature_schema_version_bad_values_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="feature_schema_version"):
        make_provenance(feature_schema_version=bad)


def test_bool_rejected_as_feature_schema_version():
    with pytest.raises(V2ProvenanceError, match="feature_schema_version"):
        make_provenance(feature_schema_version=True)


# ---- calculation_version / config_hash / config_version / code_version -----
def test_calculation_version_exact_format():
    assert make_provenance(calculation_version=H16).calculation_version == H16


@pytest.mark.parametrize("bad", ["a" * 15, "a" * 17, "A" * 16, "g" * 16, ""])
def test_calculation_version_malformed_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="calculation_version"):
        make_provenance(calculation_version=bad)


def test_config_hash_exact_format():
    assert make_provenance(config_hash=H64).config_hash == H64


@pytest.mark.parametrize("bad", ["a" * 63, "a" * 65, "A" * 64, "g" * 64, ""])
def test_config_hash_malformed_rejected(bad):
    with pytest.raises(V2ProvenanceError, match="config_hash"):
        make_provenance(config_hash=bad)


@pytest.mark.parametrize("field", ["config_version", "code_version"])
@pytest.mark.parametrize("bad", ["", "   ", None])
def test_config_and_code_version_nonblank(field, bad):
    with pytest.raises(V2ProvenanceError, match=field):
        make_provenance(**{field: bad})


# ---- purity: no clock / uuid / random / config / file / env / db access ----
def test_no_clock_uuid_random_config_file_env_db_access():
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.provenance", fromlist=["provenance"]))
    forbidden = (
        "datetime.now(", "time.time(", "uuid.uuid4(", "random.",
        "open(", "os.environ", "os.getenv", "yaml.safe_load", "asyncpg",
        "V2Config.load", "Stage2Config",
    )
    for token in forbidden:
        assert token not in src, f"forbidden token found in provenance.py: {token!r}"


def test_module_imports_no_io_libraries():
    import analytics.forecasting_v2.provenance as prov_mod
    src = textwrap.dedent(inspect.getsource(prov_mod))
    for banned_import in ("import asyncio", "import asyncpg", "import yaml",
                          "import uuid", "import random", "import os"):
        assert banned_import not in src


# ---- shared validation reuse (no duplicated hex regex) ----------------------
def test_provenance_module_defines_no_local_hex_regex():
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.provenance", fromlist=["provenance"]))
    assert "re.compile" not in src


def test_provenance_reuses_shared_validators_directly():
    from analytics.forecasting_v2 import provenance as prov_mod
    assert prov_mod.validate_calculation_version is validate_calculation_version
    assert prov_mod.validate_config_hash is validate_config_hash
    assert prov_mod.validate_feature_schema_version is validate_feature_schema_version
    assert prov_mod.validate_symbol is validate_symbol
    assert prov_mod.validate_market_type is validate_market_type
