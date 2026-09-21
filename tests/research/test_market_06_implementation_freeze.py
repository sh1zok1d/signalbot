"""MARKET-06 implementation-freeze identity checks.

Does not parse retained OHLC for science or authorize execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.market_06_cross_venue_dislocation_authority import (
    CLASS_INCOMPLETE,
    Market06ExecutionNotAuthorized,
    refuse_canonical_execution,
)


REPO = Path(__file__).resolve().parents[2]
FREEZE_JSON = (
    REPO / "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.json"
)
FREEZE_MD = (
    REPO / "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.md"
)

IMPLEMENTATION_HEAD = "81c8e0a8619190329971f5a85435c7ac4f9cb86e"
IMPLEMENTATION_TREE = "7f4e0a85dc3738924eb52bb28f85794d6a8daa7a"
PREREG_FREEZE_HEAD = "e2d543eadb5425473b6d4b8d24c177c1d7ae7930"
PREREG_FREEZE_TREE = "a1706c775154fc65ad1d5eaaa5818f87b834a2b7"

EXPECTED = {
    "scripts/research/market_06_cross_venue_dislocation_authority.py": (
        "dcfdc92843c91871317dae88d0b40e58b01387e10d52337090b543bdec44523f",
        14399,
    ),
    "scripts/research/market_06_cross_venue_dislocation_parsers.py": (
        "057a6e763aaa1f822571dd670a8e0d65c786fb4df5796fa50a12ae94c9f265c6",
        5625,
    ),
    "scripts/research/market_06_cross_venue_dislocation_bootstrap.py": (
        "773b7631f76885f34532dc16a845fd07711e9ca44496d7ef18a8079e98a63ec7",
        4557,
    ),
    "scripts/research/market_06_cross_venue_dislocation_evaluator.py": (
        "c280c609db64362ec76a5810ce0cedc25cc609ef9fdcbc87e0cd935e6d8c6545",
        17616,
    ),
    "scripts/research/market_06_cross_venue_dislocation_runner.py": (
        "e07470d1f371f0656d95d9e2116f4e5f983a416ad6f9ac8defaa619c1c416025",
        1659,
    ),
    "scripts/research/market_06_year_stratified_circular_mbb.py": (
        "e8545dab9c3cf28eba556b3a0fe36d0b06cf412437a48516b3dc038a9a082da3",
        2988,
    ),
    "tests/research/test_market_06_implementation.py": (
        "9caac63b74f661a1e6cda7d20c958666aef0d5e885d514f15f8cdf449e414e7d",
        21332,
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_implementation_freeze_binds_implementation_and_prereg_heads():
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    assert freeze["accepted_implementation"]["head"] == IMPLEMENTATION_HEAD
    assert freeze["accepted_implementation"]["tree"] == IMPLEMENTATION_TREE
    assert freeze["prereg_authority"]["prereg_freeze_head"] == PREREG_FREEZE_HEAD
    assert freeze["prereg_authority"]["prereg_freeze_tree"] == PREREG_FREEZE_TREE
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["status"] == "IMPLEMENTATION_FROZEN_OUTCOME_BLIND"
    assert freeze["explicit_state"]["market_06_execution_authorized"] is False
    assert freeze["explicit_state"]["real_canonical_execution_refused"] is True
    assert freeze["next_lifecycle_state"] == "MARKET_06_IMPLEMENTATION_RED_TEAM_REVIEW"
    md = FREEZE_MD.read_text(encoding="utf-8")
    assert "UNSET_UNTIL_THIS_COMMIT" in md
    assert IMPLEMENTATION_HEAD in md


def test_bound_module_bytes_match_freeze_inventory():
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    listed = {
        row["path"]: row
        for row in freeze["accepted_scientific_implementation"]
        + freeze["transitive_scientific_dependencies"]
        + freeze["implementation_tests"]
    }
    for rel, (digest, size) in EXPECTED.items():
        path = REPO / rel
        assert _sha256(path) == digest
        assert path.stat().st_size == size
        assert listed[rel]["sha256"] == digest
        assert listed[rel]["size_bytes"] == size


def test_execution_still_unauthorized_after_implementation_freeze():
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    assert freeze["explicit_state"]["market_06_armed"] is False
    assert freeze["explicit_state"]["market_06_executed"] is False
    assert freeze["not_an_arm"] is True
    with pytest.raises(Market06ExecutionNotAuthorized):
        refuse_canonical_execution(authorize=True)
    research = REPO / "docs" / "research"
    for name in (
        "MARKET_06_ARM.md",
        "MARKET_06_ARM.json",
        "MARKET_06_RESULT.md",
        "MARKET_06_RESULT.json",
    ):
        assert not (research / name).exists()
    assert CLASS_INCOMPLETE == "MARKET_06_INCOMPLETE_EXECUTION"
