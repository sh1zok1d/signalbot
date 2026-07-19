"""Unit tests for common/stage2_config.py."""
from __future__ import annotations

import copy

import pytest

from common.stage2_config import Stage2Config, Stage2ConfigError


def _base_raw() -> dict:
    return {
        "stage2": {"enabled": False, "config_version": "2.1.0", "feature_schema_version": 1},
        "active_exchanges": ["binance", "bybit", "okx"],
        "defaults": {
            "percentile_windows": ["7d", "30d"],
            "timeframes": ["1m", "5m", "15m", "1h", "4h"],
            "data_confidence": {
                "minimum_metric_coverage": 0.95,
                "minimum_exchange_coverage": 2,
                "weights": {"coverage": 0.50, "agreement": 0.30, "dispersion": 0.20},
            },
            "warmup": {"minimum_calendar_days": 7, "preferred_calendar_days": 30},
            "bucket_close": {"soft_grace_s": 5, "hard_deadline_s": 15},
            "outliers": {"robust_z_threshold": 3.5},
        },
        "asset_tiers": {"major": {}},
        "symbols": {"BTCUSDT": {"tier": "major", "enabled": True, "market_types": ["perp"]}},
    }


def _cfg(raw=None) -> Stage2Config:
    c = Stage2Config(raw or _base_raw())
    c._validate()
    return c


# -- real file loads and is disabled ----------------------------------------
def test_real_file_loads_and_stage2_disabled():
    cfg = Stage2Config.load()
    assert cfg.enabled is False          # read explicitly
    assert cfg.config_version == "2.1.0"
    assert cfg.feature_schema_version == 1


def test_btcusdt_resolution_only_perp():
    cfg = Stage2Config.load()
    rc = cfg.resolve("BTCUSDT")
    assert rc.symbol == "BTCUSDT"
    assert rc.tier == "major"
    assert rc.enabled is True
    assert rc.market_types == ("perp",)


# -- precedence + deep merge -------------------------------------------------
def test_defaults_tier_symbol_precedence_and_deep_merge():
    raw = _base_raw()
    raw["asset_tiers"]["major"] = {
        "warmup": {"minimum_calendar_days": 10},          # tier overrides one nested key
        "data_confidence": {"minimum_exchange_coverage": 3},
    }
    raw["symbols"]["BTCUSDT"]["warmup"] = {"preferred_calendar_days": 45}  # symbol overrides another
    rc = _cfg(raw).resolve("BTCUSDT")
    # deep merge: tier value kept, symbol value kept, default value for untouched key
    assert rc["warmup"]["minimum_calendar_days"] == 10        # from tier
    assert rc["warmup"]["preferred_calendar_days"] == 45      # from symbol
    assert rc["data_confidence"]["minimum_exchange_coverage"] == 3  # tier over default
    assert rc["data_confidence"]["minimum_metric_coverage"] == 0.95  # untouched default


def test_source_mapping_not_mutated_by_resolve():
    cfg = _cfg()
    before = copy.deepcopy(cfg._raw)
    cfg.resolve("BTCUSDT")
    assert cfg._raw == before                                # source untouched
    # mutating the independent as_dict() copy never affects the loader source
    rc = cfg.resolve("BTCUSDT")
    d = rc.as_dict()
    d["warmup"]["minimum_calendar_days"] = 999
    assert cfg._raw["defaults"]["warmup"]["minimum_calendar_days"] == 7
    assert rc["warmup"]["minimum_calendar_days"] == 7        # frozen view unaffected


def test_resolved_config_is_deeply_immutable():
    from common.stage2_config import Stage2ConfigError  # noqa: F401 (keep import local)
    rc = _cfg().resolve("BTCUSDT")
    d = rc.data
    from types import MappingProxyType
    assert isinstance(d, MappingProxyType)
    assert isinstance(d["warmup"], MappingProxyType)         # nested dict frozen
    assert isinstance(d["timeframes"], tuple)                # nested list -> tuple
    with pytest.raises(TypeError):
        d["enabled"] = False                                 # top level
    with pytest.raises(TypeError):
        d["warmup"]["minimum_calendar_days"] = 999           # nested mapping
    with pytest.raises(AttributeError):
        d["timeframes"].append("1d")                         # nested tuple


def test_as_dict_isolation():
    rc = _cfg().resolve("BTCUSDT")
    a = rc.as_dict()
    b = rc.as_dict()
    assert a is not b and a == b                             # independent copies
    a["warmup"]["minimum_calendar_days"] = -1
    assert b["warmup"]["minimum_calendar_days"] == 7         # other copy untouched
    assert rc["warmup"]["minimum_calendar_days"] == 7        # frozen view untouched


def test_immutable_and_plain_give_same_config_hash():
    from common.versioning import config_hash
    rc = _cfg().resolve("BTCUSDT")
    # hash over the frozen resolved config == hash over its plain-dict equivalent
    assert rc.config_hash() == config_hash(rc.data)
    assert rc.config_hash() == config_hash(rc.as_dict())


# -- explicit failures -------------------------------------------------------
def test_unknown_symbol_fails_no_btc_fallback():
    cfg = _cfg()
    with pytest.raises(Stage2ConfigError):
        cfg.resolve("ETHUSDT")   # must raise, never fall back to BTCUSDT


def test_unknown_tier_fails():
    raw = _base_raw()
    raw["symbols"]["BTCUSDT"]["tier"] = "nonexistent_tier"
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw).resolve("BTCUSDT")


def test_spot_market_type_fails():
    raw = _base_raw()
    raw["symbols"]["BTCUSDT"]["market_types"] = ["perp", "spot"]
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw).resolve("BTCUSDT")


def test_missing_required_keys_fail():
    raw = _base_raw()
    del raw["defaults"]["percentile_windows"]
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


def test_invalid_types_and_ranges_fail():
    raw = _base_raw()
    raw["defaults"]["data_confidence"]["minimum_exchange_coverage"] = 0   # < 1
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()
    raw2 = _base_raw()
    raw2["stage2"]["enabled"] = "false"   # str, not bool
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw2)._validate()


def test_eth_sol_not_active():
    cfg = Stage2Config.load()
    assert "ETHUSDT" not in cfg["symbols"]
    assert "SOLUSDT" not in cfg["symbols"]


# -- hash is order-independent ----------------------------------------------
def test_key_order_does_not_change_resolved_config_hash():
    raw1 = _base_raw()
    # semantically identical config with reordered keys
    raw2 = _base_raw()
    raw2["defaults"] = {
        "warmup": {"preferred_calendar_days": 30, "minimum_calendar_days": 7},
        "timeframes": ["1m", "5m", "15m", "1h", "4h"],
        "outliers": {"robust_z_threshold": 3.5},
        "data_confidence": {
            "minimum_exchange_coverage": 2, "minimum_metric_coverage": 0.95,
            "weights": {"dispersion": 0.20, "agreement": 0.30, "coverage": 0.50},
        },
        "percentile_windows": ["7d", "30d"],
        "bucket_close": {"hard_deadline_s": 15, "soft_grace_s": 5},
    }
    h1 = _cfg(raw1).config_hash("BTCUSDT")
    h2 = _cfg(raw2).config_hash("BTCUSDT")
    assert h1 == h2


# ============ Consensus Contract Revision 0.2.3 config surface ==============
def _calc_version(cfg: Stage2Config) -> str:
    """calculation_version = sha256(schema_version, config_hash, code)[:16]."""
    from common.versioning import compute_calculation_version
    return compute_calculation_version(
        cfg.feature_schema_version, cfg.config_hash("BTCUSDT"), "test-code-v1")


# -- real file carries the frozen 0.2.3 surface, still disabled --------------
def test_real_file_has_confidence_weights_and_outliers():
    cfg = Stage2Config.load()
    assert cfg.enabled is False                         # master switch stays off
    dc = cfg.resolve("BTCUSDT")["data_confidence"]
    assert dc["weights"]["coverage"] == 0.50
    assert dc["weights"]["agreement"] == 0.30
    assert dc["weights"]["dispersion"] == 0.20
    assert cfg.resolve("BTCUSDT")["outliers"]["robust_z_threshold"] == 3.5


def test_defaults_weights_are_frozen_values():
    rc = _cfg().resolve("BTCUSDT")
    w = rc["data_confidence"]["weights"]
    assert (w["coverage"], w["agreement"], w["dispersion"]) == (0.50, 0.30, 0.20)


def test_weights_in_resolved_config():
    rc = _cfg().resolve("BTCUSDT")
    assert "weights" in rc["data_confidence"]
    assert set(rc["data_confidence"]["weights"]) == {"coverage", "agreement", "dispersion"}


def test_outlier_threshold_in_resolved_config():
    rc = _cfg().resolve("BTCUSDT")
    assert rc["outliers"]["robust_z_threshold"] == 3.5


def test_config_hash_changes_when_any_weight_changes():
    base = _cfg().config_hash("BTCUSDT")
    for key in ("coverage", "agreement", "dispersion"):
        raw = _base_raw()
        # keep the sum at 1.0 by shifting weight between two components
        other = "dispersion" if key != "dispersion" else "coverage"
        raw["defaults"]["data_confidence"]["weights"][key] += 0.05
        raw["defaults"]["data_confidence"]["weights"][other] -= 0.05
        assert _cfg(raw).config_hash("BTCUSDT") != base


def test_calculation_version_changes_when_any_weight_changes():
    base = _calc_version(_cfg())
    raw = _base_raw()
    raw["defaults"]["data_confidence"]["weights"]["coverage"] = 0.60
    raw["defaults"]["data_confidence"]["weights"]["agreement"] = 0.20
    assert _calc_version(_cfg(raw)) != base


def test_config_hash_changes_when_outlier_threshold_changes():
    base = _cfg().config_hash("BTCUSDT")
    raw = _base_raw()
    raw["defaults"]["outliers"]["robust_z_threshold"] = 4.0
    assert _cfg(raw).config_hash("BTCUSDT") != base


def test_calculation_version_changes_when_outlier_threshold_changes():
    base = _calc_version(_cfg())
    raw = _base_raw()
    raw["defaults"]["outliers"]["robust_z_threshold"] = 4.0
    assert _calc_version(_cfg(raw)) != base


# -- weight validation -------------------------------------------------------
def test_negative_weight_rejected():
    raw = _base_raw()
    raw["defaults"]["data_confidence"]["weights"] = {
        "coverage": 1.10, "agreement": -0.10, "dispersion": 0.0}
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_inf_weight_rejected(bad):
    raw = _base_raw()
    raw["defaults"]["data_confidence"]["weights"]["coverage"] = bad
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


def test_weights_not_summing_to_one_rejected():
    raw = _base_raw()
    raw["defaults"]["data_confidence"]["weights"] = {
        "coverage": 0.50, "agreement": 0.30, "dispersion": 0.30}   # sum 1.10
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


def test_zero_coverage_weight_rejected():
    raw = _base_raw()
    raw["defaults"]["data_confidence"]["weights"] = {
        "coverage": 0.0, "agreement": 0.50, "dispersion": 0.50}     # sums to 1 but coverage==0
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


def test_bool_weight_rejected():
    raw = _base_raw()
    raw["defaults"]["data_confidence"]["weights"]["coverage"] = True
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


def test_missing_weights_rejected():
    raw = _base_raw()
    del raw["defaults"]["data_confidence"]["weights"]
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


def test_unknown_weight_key_rejected():
    raw = _base_raw()
    raw["defaults"]["data_confidence"]["weights"]["freshness"] = 0.0
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


# -- outlier threshold validation --------------------------------------------
@pytest.mark.parametrize("bad", [0.0, -1.0, -0.001])
def test_nonpositive_outlier_threshold_rejected(bad):
    raw = _base_raw()
    raw["defaults"]["outliers"]["robust_z_threshold"] = bad
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nan_inf_outlier_threshold_rejected(bad):
    raw = _base_raw()
    raw["defaults"]["outliers"]["robust_z_threshold"] = bad
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


def test_missing_outliers_rejected():
    raw = _base_raw()
    del raw["defaults"]["outliers"]
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


# -- nested immutability of the new config -----------------------------------
def test_new_nested_config_is_deeply_immutable():
    from types import MappingProxyType
    rc = _cfg().resolve("BTCUSDT")
    weights = rc["data_confidence"]["weights"]
    outliers = rc["outliers"]
    assert isinstance(weights, MappingProxyType)
    assert isinstance(outliers, MappingProxyType)
    with pytest.raises(TypeError):
        weights["coverage"] = 0.99
    with pytest.raises(TypeError):
        outliers["robust_z_threshold"] = 9.0


def test_stage2_remains_disabled_after_freeze():
    assert Stage2Config.load().enabled is False


# -- SHOULD FIX: unknown outlier keys are rejected (no silent ignore) --------
def test_unknown_outlier_key_rejected():
    # an arbitrary extra key
    raw = _base_raw()
    raw["defaults"]["outliers"]["scale"] = 0.67
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()

    # a typo of the canonical key must NOT be silently accepted
    raw2 = _base_raw()
    raw2["defaults"]["outliers"]["robust_z_treshold"] = 5.0   # missing 'h'
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw2)._validate()

    # the error message lists the unknown keys in deterministic sorted order
    raw3 = _base_raw()
    raw3["defaults"]["outliers"]["zzz"] = 1
    raw3["defaults"]["outliers"]["aaa"] = 2
    with pytest.raises(Stage2ConfigError) as exc:
        Stage2Config(raw3)._validate()
    assert "['aaa', 'zzz']" in str(exc.value)

    # the canonical key on its own still works
    ok = _base_raw()
    ok["defaults"]["outliers"] = {"robust_z_threshold": 3.5}
    Stage2Config(ok)._validate()          # does not raise


def test_bool_outlier_threshold_rejected():
    for bad in (True, False):
        raw = _base_raw()
        raw["defaults"]["outliers"]["robust_z_threshold"] = bad
        with pytest.raises(Stage2ConfigError):
            Stage2Config(raw)._validate()


def test_string_numeric_values_not_coerced():
    # numeric-looking strings must be rejected, never float()-coerced
    for key, val in (("coverage", "0.5"), ("agreement", "0.3"), ("dispersion", "0.2")):
        raw = _base_raw()
        raw["defaults"]["data_confidence"]["weights"][key] = val
        with pytest.raises(Stage2ConfigError):
            Stage2Config(raw)._validate()
    raw = _base_raw()
    raw["defaults"]["outliers"]["robust_z_threshold"] = "3.5"
    with pytest.raises(Stage2ConfigError):
        Stage2Config(raw)._validate()


def test_weight_sum_tolerance_boundary():
    # within tolerance (1e-9): deviation 1e-12 << tol -> accepted.
    ok = _base_raw()
    ok["defaults"]["data_confidence"]["weights"] = {
        "coverage": 0.5, "agreement": 0.3, "dispersion": 0.2 + 1e-12}
    Stage2Config(ok)._validate()          # does not raise

    # clearly beyond tolerance: deviation 1e-6 >> tol -> rejected.
    bad = _base_raw()
    bad["defaults"]["data_confidence"]["weights"] = {
        "coverage": 0.5, "agreement": 0.3, "dispersion": 0.2 + 1e-6}
    with pytest.raises(Stage2ConfigError):
        Stage2Config(bad)._validate()


def test_nonfinite_outlier_threshold_rejected():
    for bad in (float("nan"), float("inf"), float("-inf")):
        raw = _base_raw()
        raw["defaults"]["outliers"]["robust_z_threshold"] = bad
        with pytest.raises(Stage2ConfigError):
            Stage2Config(raw)._validate()
