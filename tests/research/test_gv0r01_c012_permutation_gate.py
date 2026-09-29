"""Timestamp-only C012 permutation gate. Must not open a price file."""

import json
from pathlib import Path

from scripts.research import gv0r01_c012_execute as EX
from scripts.research.gv0r01_c012_permutation_gate import gate_from_pairs

BLOCK = Path("docs/research/GV0R01_C012_DEPENDENCE_BLOCK.json")


def test_global_exchangeability_is_not_established_from_timestamps():
    pre = json.loads(EX.PREFLIGHT_JSON.read_text())
    gate = gate_from_pairs(pre["PAIRS"])
    assert gate["GLOBAL_OVERLAP_GRAPH_COMPONENTS"] == 177
    assert gate["MAX_OVERLAP_COMPONENT_SIZE"] == 2
    assert gate["SWAPPABLE_PAIRS_WITH_DIFFERENT_EXTERNAL_NEIGHBORHOODS"] == 240
    assert gate["SWAPPABLE_OBSERVATIONS_WITH_DIFFERENT_EXTERNAL_NEIGHBORHOODS"] == 154
    assert gate["GLOBAL_PERMUTATION_INVARIANCE_STATUS"] == "NOT_ESTABLISHED"
    block = json.loads(BLOCK.read_text())
    assert block["RUN_STATUS"] == "BLOCKED_INFERENCE_DEPENDENCE_DEFECT"
    assert block["MARKET_DATA_OPENED_FOR_C012"] is False
    assert block["C012_PRIMARY_TEST_EXECUTED"] is False
    assert block["PRIMARY_EFFECT"] == "NOT_COMPUTED"
    assigned = EX.assign_controls(json.loads(EX.CONTRACT.read_text())["EVENTS"])
    assert [(p["EVENT_ID"], p["CONTROL_WINDOW_END_UTC"]) for p in assigned["PAIRS"]] == [
        (p["EVENT_ID"], p["CONTROL_WINDOW_END_UTC"]) for p in pre["PAIRS"]
    ]
