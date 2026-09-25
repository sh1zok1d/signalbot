"""Outcome-blind C012 inference amendment. Must not open a price file."""

import json
from pathlib import Path

import numpy as np

from scripts.research import gv0r01_c012_inference_amendment as AM

AMENDMENT = Path("docs/research/GV0R01_C012_INFERENCE_AMENDMENT.json")


def _graph():
    rows = AM.load_rows()
    graph = AM.build_graph(rows)
    summary = AM.group_and_orbit(AM.structural_factors(graph))
    return graph, summary


def test_graph_counts_match_the_dependence_block():
    graph, summary = _graph()
    assert len(graph["order"]) == 198
    assert len(graph["edges"]) == 21
    assert sum(1 for d in graph["degrees"] if d == 0) + len(graph["edges"]) == 177
    assert max(graph["degrees"]) == 2 or max(graph["degrees"]) == 1
    block = json.loads(Path("docs/research/GV0R01_C012_DEPENDENCE_BLOCK.json").read_text())
    assert block["GLOBAL_OVERLAP_GRAPH_COMPONENTS"] == 177
    assert block["MAX_OVERLAP_COMPONENT_SIZE"] == 2
    assert summary["OBSERVATIONS_THAT_CAN_CHANGE_LABEL"] == 170
    assert summary["OBSERVATIONS_FIXED_BY_TOPOLOGY"] == 28
    assert summary["EVENT_LABELS_MOBILE"] == 95
    assert summary["CONTROL_LABELS_MOBILE"] == 75


def test_generated_permutations_preserve_stratum_and_adjacency():
    graph, summary = _graph()
    adj = AM.adjacency_matrix(graph)
    rng = np.random.default_rng(AM.PERMUTATION_SEED)
    for _ in range(25):
        pi = AM.explicit_permutation(graph, summary, rng)
        assert AM.preserves_stratum_and_adjacency(graph, pi, adj)


def test_known_invalid_swap_and_all_240_breaking_swaps_are_rejected():
    graph, _summary = _graph()
    adj = AM.adjacency_matrix(graph)
    a, b = AM.known_invalid_swap_ids()
    assert AM.transposition_preserves(graph, adj, a, b) is False
    bad = AM.topology_breaking_pairs(graph)
    assert len(bad) == 240
    assert all(not AM.transposition_preserves(graph, adj, x, y) for x, y in bad)


def test_orbit_and_sampling_are_deterministic():
    graph, summary = _graph()
    again = AM.group_and_orbit(AM.structural_factors(graph))
    assert summary["PRIMARY_LABEL_ORBIT_SIZE"] == again["PRIMARY_LABEL_ORBIT_SIZE"]
    assert summary["TOPOLOGY_GROUP_SIZE"] == again["TOPOLOGY_GROUP_SIZE"]
    assert summary["PRIMARY_LABEL_ORBIT_SIZE"] > 10**20
    a = AM.sample_label_matrix(graph, summary, np.random.default_rng(AM.PERMUTATION_SEED), 8)
    b = AM.sample_label_matrix(graph, summary, np.random.default_rng(AM.PERMUTATION_SEED), 8)
    assert np.array_equal(a, b)
    assert np.all(a.sum(axis=1) == 99)


def test_monte_carlo_p_is_never_zero():
    stats = np.array([0.0, 0.0, 0.0])
    p = AM.monte_carlo_p(np.zeros(1), stats, 0.0)
    assert p == 1.0
    p2 = AM.monte_carlo_p(np.zeros(1), np.array([0.1]), 5.0)
    assert p2 == (1.0 + 0.0) / 2.0
    assert p2 > 0.0


def test_bar_boundary_matches_frozen_close_definition():
    stamps = AM.price_timestamps("2020-05-12T12:29:00Z")
    assert stamps["LAST_PRICE_OPEN_TIME_UNIX"] - stamps["FIRST_PRICE_OPEN_TIME_UNIX"] == 86400
    assert stamps["CONTRIBUTING_MINUTE_COUNT"] == 1440
    assert stamps["EXCLUDED_BAR_OPEN_UNIX"] == stamps["LAST_PRICE_OPEN_TIME_UNIX"]
    boundary = AM.bar_boundary_contract()
    assert boundary["EVENT_WINDOW_CONTRIBUTING_MINUTE_COUNT"] == 1440
    assert boundary["CONTROL_WINDOW_CONTRIBUTING_MINUTE_COUNT"] == 1440
    assert boundary["EVENT_WINDOW_FIRST_PRICE_TIMESTAMP_RULE"] == boundary["CONTROL_WINDOW_FIRST_PRICE_TIMESTAMP_RULE"]
    assert boundary["EVENT_WINDOW_LAST_PRICE_TIMESTAMP_RULE"] == boundary["CONTROL_WINDOW_LAST_PRICE_TIMESTAMP_RULE"]


def test_contract_freezes_endpoint_events_and_power_gate_without_prices():
    src = Path(AM.__file__).read_text()
    assert "read_parquet" not in src
    assert "load_btc_closes" not in src
    assert "2025-01" not in src or "PROTECTED" in src
    doc = json.loads(AMENDMENT.read_text())
    design = json.loads(Path("docs/research/GV0R01_C012_OUTCOME_BLIND_DESIGN.json").read_text())
    assert doc["PRIMARY_ENDPOINT"] == "DELTA_24"
    assert doc["EVENT_COUNT"] == 99
    assert doc["CONTROL_COUNT"] == 99
    assert design["UNIVERSE_SUMMARY"]["EVENT_N"] == 99
    assert doc["MARKET_DATA_OPENED_FOR_C012"] is False
    assert doc["C012_PRIMARY_TEST_EXECUTED"] is False
    assert doc["PROTECTED_2025_VALUES_OPENED"] is False
    assert doc["PROTECTED_2026_VALUES_OPENED"] is False
    assert doc["POWER_GATE"]["AMENDED_POWER_GATE_RESULT"] == "INFERENCE_AMENDMENT_VALID_BUT_INFORMATIONALLY_WEAK"
    assert doc["POWER_GATE"]["MDE_SINGLE_WINDOW_SD_UNITS"] > 0.50
    assert doc["NEXT_UNIT"] == "NO_EXECUTION_AUTHORIZED"
    assert "CORE_BTC" not in src
