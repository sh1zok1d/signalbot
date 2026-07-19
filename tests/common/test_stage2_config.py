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
            "data_confidence": {"minimum_metric_coverage": 0.95, "minimum_exchange_coverage": 2},
            "warmup": {"minimum_calendar_days": 7, "preferred_calendar_days": 30},
            "bucket_close": {"soft_grace_s": 5, "hard_deadline_s": 15},
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
        "data_confidence": {"minimum_exchange_coverage": 2, "minimum_metric_coverage": 0.95},
        "percentile_windows": ["7d", "30d"],
        "bucket_close": {"hard_deadline_s": 15, "soft_grace_s": 5},
    }
    h1 = _cfg(raw1).config_hash("BTCUSDT")
    h2 = _cfg(raw2).config_hash("BTCUSDT")
    assert h1 == h2
