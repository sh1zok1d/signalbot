from __future__ import annotations

from types import MappingProxyType

from scripts.research.v2_e1_development_ablation_inventory_vps import _thaw_jsonlike


def test_thaw_jsonlike_handles_nested_mappingproxy_without_mutating_source():
    nested = MappingProxyType({"ratio": 2.0 / 3.0})
    coverage = MappingProxyType({"taker_flow": nested, "price_structure": {"ratio": 1.0}})
    source = MappingProxyType({
        "coverage_by_metric": coverage,
        "data_confidence_by_metric": MappingProxyType({
            "taker_flow": 75.0,
            "price_structure": 90.0,
        }),
        "taker_delta_notional_usd_sum": 123.0,
    })

    thawed = _thaw_jsonlike(source)

    assert type(thawed) is dict
    assert type(thawed["coverage_by_metric"]) is dict
    assert type(thawed["coverage_by_metric"]["taker_flow"]) is dict
    assert thawed["coverage_by_metric"]["taker_flow"]["ratio"] == 2.0 / 3.0

    thawed["coverage_by_metric"]["taker_flow"]["ratio"] = 1.0
    thawed["data_confidence_by_metric"]["taker_flow"] = 100.0

    assert source["coverage_by_metric"]["taker_flow"]["ratio"] == 2.0 / 3.0
    assert source["data_confidence_by_metric"]["taker_flow"] == 75.0
