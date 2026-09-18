"""MARKET-03 source-feasibility tests.

Does not run EmaCross/EmaCrossFunding, load CORE/OI snapshots, or compute
any Signalbot strategy outcome.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY.md"
JS = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY.json"
INV = REPO / "docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/SOURCE_INVENTORY.json"
SRC = REPO / "docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/source"

EXPECTED_COMMIT = "b68a5518b4a3eba2fde1733160d7d7de356023b5"
EXPECTED_TREE = "f7717e681c911ea3ccce15492246053cf15883cb"
MATERIAL = {
    "user_data/strategies/EmaCross.py": "387cf39f58d266bb63d06865a0784bc2e08676edf54f4610c7d7709bb2a95f24",
    "user_data/strategies/EmaCrossFunding.py": "0f0d3d4677647da2e11d4dc8195adbb95fce201ce400300df0a78741cf9a9564",
    "user_data/strategies/EmaCross.json": "9209a90e5092216af166fd10b9e7415690ab16af0fb3010c7e94e162c027e3ee",
    "user_data/strategies/EmaCrossFunding.json": "1641ce3122ccc0c216aaae1af77bedb15dd77670643201d1c7453066eca38f0b",
    "config.json": "a20cfbf8c9efa36b06f336ef772e8be905e9c236b6f7bed38a4a0a810879ecda",
    "research/fetch_onchain.py": "2312dc978cc62b8b3acd1f75226bd1f51292704d2758fb01eb4d9ead06d876bf",
    "research/metrics.py": "982b76ff2ab8bcac0b1512015dbad9125edf5cbfde8f8af9bff0183251bc44e8",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pinned_commit_and_verdict():
    payload = json.loads(JS.read_text(encoding="utf-8"))
    assert payload["external_source"]["commit_sha"] == EXPECTED_COMMIT
    assert payload["external_source"]["commit_tree"] == EXPECTED_TREE
    assert payload["feasibility_verdict"] == "DATA_ACQUISITION_REQUIRED"
    assert payload["replication_level_with_current_snapshots"] == "NOT_FEASIBLE"
    assert payload["MARKET_03_PREREG"] is False
    assert payload["MARKET_03_ARMED"] is False
    assert payload["MARKET_03_EXECUTED"] is False
    assert payload["MARKET_03_RESULT_CREATED"] is False
    assert payload["PROTECTED_OOS_TOUCHED"] is False
    assert payload["B2_06_EXECUTION_AUTHORIZED"] is False
    assert payload["signalbot_compatibility"]["spot_dataset_exists"] is False
    assert payload["signalbot_compatibility"]["silent_perp_for_spot_forbidden"] is True
    assert payload["funding_lookahead"]["do_not_invent_publication_timing"] is True
    text = MD.read_text(encoding="utf-8")
    assert EXPECTED_COMMIT in text
    assert "DATA_ACQUISITION_REQUIRED" in text
    assert "VERDICT = DATA_ACQUISITION_REQUIRED" in text


def test_captured_source_hashes_match_inventory():
    inventory = json.loads(INV.read_text(encoding="utf-8"))
    assert inventory["external_commit_sha"] == EXPECTED_COMMIT
    by_path = {row["path"]: row for row in inventory["files"]}
    for rel, digest in MATERIAL.items():
        assert by_path[rel]["sha256"] == digest
        copied = SRC / rel
        assert copied.is_file()
        assert _sha256(copied) == digest


def test_outcome_blindness_flags_are_all_false():
    payload = json.loads(JS.read_text(encoding="utf-8"))
    flags = payload["outcome_blindness"]
    assert flags == {
        "strategy_trades": False,
        "strategy_return": False,
        "drawdown": False,
        "sharpe": False,
        "candidate_comparison": False,
        "emacross_performance": False,
        "emacrossfunding_performance": False,
        "parameter_sensitivity": False,
    }


def test_json_is_canonical_sorted_keys():
    raw = JS.read_bytes()
    payload = json.loads(raw)
    replay = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    assert raw == replay
