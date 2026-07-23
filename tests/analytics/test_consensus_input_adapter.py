"""Unit tests for analytics/feature_engine/consensus_input_adapter.py.

Pure/deterministic — no DB, network, clock. Uses the real Stage2Config, the real
ExchangeFeatureVector / ConsensusFeatureRequest models, and the real consensus
core only where an integration assertion is warranted. The semantic consensus
algorithm itself is NOT re-implemented here.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.feature_engine.consensus_models import (
    ConsensusFeatureRequest, FAMILIES,
)
from analytics.feature_engine.consensus import compute_consensus_features, ConsensusError
from analytics.feature_engine.consensus_input_adapter import (
    ConsensusInputError, build_consensus_feature_request,
)

CFG = Stage2Config.load()
BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
CODE = "code-v1"
CH = CFG.resolve("BTCUSDT").config_hash()                 # authoritative config_hash
FSV = CFG.feature_schema_version                          # 1
CVER = CFG.config_version                                 # '2.1.0'
CV = compute_calculation_version(FSV, CH, CODE)           # authoritative calc version
EXS = ("binance", "bybit", "okx")
LQ = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _efv(ex, **over):
    base = dict(
        exchange=ex, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=BASE, feature_schema_version=FSV, calculation_version=CV,
        price_move_pct=1.0, range_width_pct=5.0, close_price=100.0,
        volume_raw=10.0, volume_raw_unit="base", volume_notional_usd=1000.0,
        taker_buy_notional_usd=600.0, taker_sell_notional_usd=400.0,
        taker_delta_notional_usd=200.0, cvd_delta_notional_usd=200.0,
        oi_change_pct=2.0, oi_unit="base", funding_rate=0.0001,
        long_liquidation_notional=0.0, short_liquidation_notional=0.0,
        liquidation_event_count=0, liquidation_feed_quality=LQ[ex],
        is_snapshot_feed=(ex == "binance"),
        bars_expected=5, bars_present=5, has_gap=False, is_usable=True,
        config_hash=CH, config_version=CVER, code_version=CODE)
    base.update(over)
    return ExchangeFeatureVector(**base)


def _exp(**over):
    exp = {f: EXS for f in FAMILIES}
    exp.update(over)
    return exp


def _build(features, *, expected=None, exclusions=None, cfg=CFG):
    return build_consensus_feature_request(
        cfg, exchange_features=features,
        expected_exchanges_by_family=(expected if expected is not None else _exp()),
        exclusion_reasons_by_family=(exclusions if exclusions is not None else {}))


def _disabled_cfg():
    raw = copy.deepcopy(CFG._raw)
    raw["symbols"]["BTCUSDT"]["enabled"] = False
    cfg = Stage2Config(raw)
    cfg._validate()
    return cfg


# ============================================================================
# A. Happy path
# ============================================================================
def test_valid_three_exchange_request_has_authoritative_fields():
    req = _build([_efv("binance"), _efv("bybit"), _efv("okx")])
    assert isinstance(req, ConsensusFeatureRequest)
    assert req.symbol == "BTCUSDT" and req.market_type == "perp"
    assert req.timeframe == "5m" and req.bucket_ts == BASE
    assert req.code_version == CODE
    assert req.feature_schema_version == FSV
    assert req.config_hash == CH and req.config_version == CVER
    assert req.calculation_version == CV
    # resolved consensus thresholds come from config, not the caller
    assert req.minimum_exchange_coverage == CFG.resolve("BTCUSDT")["data_confidence"]["minimum_exchange_coverage"]
    assert dict(req.confidence_weights) == dict(CFG.resolve("BTCUSDT")["data_confidence"]["weights"])
    assert req.robust_z_threshold == CFG.resolve("BTCUSDT")["outliers"]["robust_z_threshold"]


def test_valid_two_exchange_partial_with_explicit_exclusion():
    req = _build([_efv("binance"), _efv("bybit")],
                 exclusions={f: {"okx": "NO_DATA"} for f in FAMILIES})
    # expected denominator preserved verbatim (still all three), exclusion kept
    for f in FAMILIES:
        assert tuple(req.expected_exchanges_by_family[f]) == EXS
        assert dict(req.exclusion_reasons_by_family[f]) == {"okx": "NO_DATA"}
    # and the real core accepts it (integration sanity, not a re-implementation)
    v = compute_consensus_features(req)
    assert v.is_partial_consensus is True


def test_first_efv_supplies_identity():
    # only the FIRST vector's identity is authoritative; a second matching vector
    # is fine. Build with binance first.
    req = _build([_efv("binance"), _efv("bybit")])
    assert req.symbol == "BTCUSDT" and req.timeframe == "5m" and req.code_version == CODE


def test_expected_and_exclusions_preserved_exactly():
    exp = _exp(oi=("binance", "bybit"))            # a custom per-family denominator
    excl = {"funding": {"okx": "STALE"}}
    req = _build([_efv("binance"), _efv("bybit"), _efv("okx")], expected=exp, exclusions=excl)
    assert tuple(req.expected_exchanges_by_family["oi"]) == ("binance", "bybit")
    assert tuple(req.expected_exchanges_by_family["volume"]) == EXS
    assert dict(req.exclusion_reasons_by_family["funding"]) == {"okx": "STALE"}


def test_stage2_disabled_does_not_block_construction():
    assert CFG.enabled is False
    req = _build([_efv("binance"), _efv("bybit"), _efv("okx")])
    assert req.calculation_version == CV


def test_deterministic_repeated_calls_are_equal():
    feats = [_efv("binance"), _efv("bybit"), _efv("okx")]
    assert _build(feats) == _build(feats)


def test_input_order_matches_core_determinism_contract():
    a = compute_consensus_features(_build([_efv("binance"), _efv("bybit"), _efv("okx")]))
    b = compute_consensus_features(_build([_efv("okx"), _efv("binance"), _efv("bybit")]))
    assert a == b


def test_inputs_not_mutated():
    feats = [_efv("binance"), _efv("bybit")]
    first = feats[0]
    exp = _exp()
    excl = {"oi": {"okx": "NO_DATA"}}
    exp_before = copy.deepcopy({k: tuple(v) for k, v in exp.items()})
    _build(feats, expected=exp, exclusions=excl)
    assert feats[0] is first and len(feats) == 2
    assert {k: tuple(v) for k, v in exp.items()} == exp_before
    assert excl == {"oi": {"okx": "NO_DATA"}}


# ============================================================================
# B. exchange_features container validation
# ============================================================================
def _gen():
    yield _efv("binance")


_BAD_CONTAINERS = [
    None, True, False, 0, 3.5, "", "abc", b"", b"x", bytearray(b"x"),
    {"binance": 1}, set(), frozenset(), _gen(), iter([_efv("binance")]),
    object(), [], (),
]


@pytest.mark.parametrize("bad", _BAD_CONTAINERS, ids=lambda b: type(b).__name__)
def test_exchange_features_bad_container_rejected(bad):
    with pytest.raises(ConsensusInputError):
        build_consensus_feature_request(
            CFG, exchange_features=bad,
            expected_exchanges_by_family=_exp(), exclusion_reasons_by_family={})


def test_exchange_features_malformed_row_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance"), object()])


def test_exchange_features_mixed_valid_and_malformed_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance"), {"exchange": "bybit"}])


# ============================================================================
# C. identity / version mismatch (each field independently)
# ============================================================================
def test_symbol_mismatch_between_efvs_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance"), _efv("bybit", symbol="ETHUSDT")])


def test_market_type_mismatch_between_efvs_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance"), _efv("bybit", market_type="spot")])


def test_timeframe_mismatch_between_efvs_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance"), _efv("bybit", timeframe="1h")])


def test_bucket_ts_mismatch_between_efvs_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance"), _efv("bybit", bucket_ts=BASE + timedelta(minutes=5))])


def test_code_version_mismatch_between_efvs_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance"), _efv("bybit", code_version="other")])


def test_config_hash_mismatch_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance", config_hash="b" * 64), _efv("bybit")])


def test_config_version_mismatch_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance", config_version="9.9.9"), _efv("bybit")])


def test_feature_schema_version_mismatch_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance", feature_schema_version=2), _efv("bybit")])


def test_calculation_version_mismatch_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance", calculation_version="0" * 16), _efv("bybit")])


# ============================================================================
# D. config validation
# ============================================================================
@pytest.mark.parametrize("bad", [object(), None, {"stage2": {}}, "cfg"])
def test_not_a_stage2_config_rejected(bad):
    with pytest.raises(ConsensusInputError):
        build_consensus_feature_request(
            bad, exchange_features=[_efv("binance")],
            expected_exchanges_by_family=_exp(), exclusion_reasons_by_family={})


def test_unknown_symbol_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance", symbol="DOGEUSDT")])


def test_resolved_disabled_symbol_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance"), _efv("bybit")], cfg=_disabled_cfg())


def test_unsupported_market_type_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance", market_type="spot")])


def test_unsupported_timeframe_rejected():
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance", timeframe="3m")])


def test_authoritative_version_derivation_ignores_efv_supplied_versions():
    # every EFV carries the CORRECT derived versions, and the request mirrors the
    # config-derived values (not something a caller could have invented).
    req = _build([_efv("binance")])
    assert req.config_hash == CFG.resolve("BTCUSDT").config_hash()
    assert req.calculation_version == compute_calculation_version(
        CFG.feature_schema_version, req.config_hash, CODE)


def test_caller_cannot_smuggle_inconsistent_calc_version_via_first_efv():
    # first EFV pretends to a different calc/config version -> mismatch vs derived
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance", calculation_version="a" * 16, config_hash="c" * 64)])


# ============================================================================
# E. explicit denominator behaviour
# ============================================================================
def test_denominator_not_inferred_from_present_efvs():
    # only 2 EFVs present, but caller's expected set still names all three
    req = _build([_efv("binance"), _efv("bybit")],
                 exclusions={f: {"okx": "NO_DATA"} for f in FAMILIES})
    for f in FAMILIES:
        assert tuple(req.expected_exchanges_by_family[f]) == EXS   # 3, not 2


def test_denominator_not_inferred_from_registry():
    # caller shrinks the denominator to two venues; adapter must not re-add okx
    exp = {f: ("binance", "bybit") for f in FAMILIES}
    req = _build([_efv("binance"), _efv("bybit")], expected=exp)
    for f in FAMILIES:
        assert tuple(req.expected_exchanges_by_family[f]) == ("binance", "bybit")


def test_adapter_does_not_autopopulate_exclusions():
    # an absent-but-expected exchange requires a CALLER exclusion; the adapter
    # never guesses one — the exclusion map stays exactly what the caller passed.
    req = _build([_efv("binance"), _efv("bybit")],
                 exclusions={f: {"okx": "NO_DATA"} for f in FAMILIES})
    assert dict(req.exclusion_reasons_by_family["oi"]) == {"okx": "NO_DATA"}
    # and with no exclusion supplied, none is invented (the core will then reject)
    req2 = _build([_efv("binance"), _efv("bybit"), _efv("okx")])
    assert dict(req2.exclusion_reasons_by_family) == {}


def test_replay_denominator_unchanged_verbatim():
    exp = _exp(liquidations=("binance",))
    req = _build([_efv("binance"), _efv("bybit"), _efv("okx")], expected=exp,
                 exclusions={"liquidations": {}})
    assert tuple(req.expected_exchanges_by_family["liquidations"]) == ("binance",)


@pytest.mark.parametrize("bad_expected", [None, [], "x", 5, {"oi", "funding"}])
def test_malformed_expected_outer_container_rejected(bad_expected):
    with pytest.raises(ConsensusInputError):
        build_consensus_feature_request(
            CFG, exchange_features=[_efv("binance")],
            expected_exchanges_by_family=bad_expected, exclusion_reasons_by_family={})


@pytest.mark.parametrize("bad_members", ["binance", b"binance", 5, None])
def test_malformed_expected_inner_container_rejected(bad_members):
    exp = _exp(oi=bad_members)
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance")], expected=exp)


@pytest.mark.parametrize("bad_excl", [None, [], "x", 5])
def test_malformed_exclusion_outer_container_rejected(bad_excl):
    with pytest.raises(ConsensusInputError):
        build_consensus_feature_request(
            CFG, exchange_features=[_efv("binance")],
            expected_exchanges_by_family=_exp(), exclusion_reasons_by_family=bad_excl)


@pytest.mark.parametrize("bad_inner", ["reason", 5, ["okx"]])
def test_malformed_exclusion_inner_container_rejected(bad_inner):
    with pytest.raises(ConsensusInputError):
        _build([_efv("binance")], exclusions={"oi": bad_inner})


# ============================================================================
# F. purity / architecture
# ============================================================================
_FORBIDDEN_MODULES = {
    "storage", "asyncpg", "asyncio", "socket", "requests", "redis", "os",
    "subprocess", "time", "aiohttp", "main", "data_ingestion", "backfill",
}


def test_adapter_module_has_no_forbidden_imports_or_calls():
    src = Path("analytics/feature_engine/consensus_input_adapter.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & _FORBIDDEN_MODULES), imported & _FORBIDDEN_MODULES
    banned_attrs = {"now", "utcnow", "time", "today"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                assert f.attr not in banned_attrs, f"calls .{f.attr}()"
            if isinstance(f, ast.Name):
                assert f.id != "open", "calls open()"
