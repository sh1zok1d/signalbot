"""Outcome-blind MARKET-03 prereg freeze identity checks.

Does not inspect MARKET outcomes, execute MARKET-03, or implement the
strategy. Binds freeze-authority hashes to the frozen prereg bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PREREG_MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
PREREG_JSON = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
FREEZE_JSON = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.json"
FREEZE_MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.md"

EXPECTED_MD_SHA256 = (
    "044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57"
)
EXPECTED_JSON_SHA256 = (
    "3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89"
)
MATERIALIZATION_HEAD = "06d6ec0121a9a35f8ee947fbe89e37e97388b6e2"
MATERIALIZATION_TREE = "50bc810eb127ea7aea1843ef2ede0dd4fe8905d1"
PRE_PREREG_HEAD = "9454af65398df1d3f5e0cb3af5e48c0986049d2d"
PRE_PREREG_TREE = "27531689a1185dda7946f6742d725a87477911e2"
EXPECTED_COMMIT = "b68a5518b4a3eba2fde1733160d7d7de356023b5"
EXPECTED_SPOT = (
    "2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze() -> dict:
    return json.loads(FREEZE_JSON.read_text(encoding="utf-8"))


def test_market_03_prereg_byte_identity_matches_materialization():
    assert _sha256(PREREG_MD) == EXPECTED_MD_SHA256
    assert _sha256(PREREG_JSON) == EXPECTED_JSON_SHA256
    assert PREREG_MD.stat().st_size == 15063
    assert PREREG_JSON.stat().st_size == 15587


def test_market_03_freeze_binds_exact_paths_and_hashes():
    freeze = _freeze()
    md = freeze["frozen_prereg_artifacts"]["MARKET_03_PUBLIC_STRATEGY_PREREG.md"]
    js = freeze["frozen_prereg_artifacts"]["MARKET_03_PUBLIC_STRATEGY_PREREG.json"]
    assert md["path"] == "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
    assert js["path"] == "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
    assert md["sha256"] == EXPECTED_MD_SHA256
    assert js["sha256"] == EXPECTED_JSON_SHA256
    assert md["sha256"] == _sha256(PREREG_MD)
    assert js["sha256"] == _sha256(PREREG_JSON)
    assert freeze["accepted_prereg_content"]["head"] == MATERIALIZATION_HEAD
    assert freeze["accepted_prereg_content"]["tree"] == MATERIALIZATION_TREE
    assert freeze["pre_prereg"]["head"] == PRE_PREREG_HEAD
    assert freeze["pre_prereg"]["tree"] == PRE_PREREG_TREE
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"


def test_market_03_freeze_status_frozen_not_executed():
    freeze = _freeze()
    assert freeze["status"] == "FROZEN_OUTCOME_BLIND"
    state = freeze["explicit_state"]
    assert state["market_03_prereg_frozen"] is True
    assert state["market_03_freeze_required"] is False
    assert state["market_03_prereg_materialized"] is True
    assert state["market_03_outcome_inspected"] is False
    assert state["market_03_executed"] is False
    assert state["market_03_armed"] is False
    assert state["market_03_execution_authorized"] is False
    assert state["canonical_executions_authorized"] == 0
    assert state["canonical_executions_consumed"] == 0
    assert state["funding_snapshot_ready"] is False
    assert state["protected_oos_touched"] is False
    assert state["b2_06_execution_authorized"] is False
    assert freeze["not_an_arm"] is True
    assert freeze["not_market_03_execution"] is True
    assert freeze["next_lifecycle_state"] == "MARKET-03_IMPLEMENTATION"
    for forbidden in freeze["forbidden_outcome_dependent_labels"]:
        assert freeze["status"] != forbidden
        assert freeze["next_lifecycle_state"] != forbidden


def test_market_03_freeze_preserves_source_spot_oos_and_assumption():
    freeze = _freeze()
    src = freeze["external_source_crosscheck"]
    assert src["commit"] == EXPECTED_COMMIT
    assert src["tree"] == "f7717e681c911ea3ccce15492246053cf15883cb"
    data = freeze["data_authorities_crosscheck"]
    assert data["spot"]["snapshot_id"] == EXPECTED_SPOT
    assert data["evaluation_interval"]["end_exclusive"] == "2025-01-01T00:00:00Z"
    assert data["funding"]["b2_06_is_not_market_03_authority"] is True
    assert data["funding"]["funding_snapshot_ready"] is False
    limits = freeze["limitations_preserved"]
    assert limits["STRICT_HISTORICAL_PUBLICATION_LATENCY"] == "UNPROVEN"
    assert limits["REPRODUCTION_FUNDINGTIME_ASSUMPTION"] == "ACCEPTABLE"
    assert limits["p_value_bootstrap_gate"] is False
    metric = freeze["primary_metric_crosscheck"]
    assert "MDD_filtered > MDD_baseline" in metric["equation"]
    md = FREEZE_MD.read_text(encoding="utf-8")
    assert EXPECTED_COMMIT in md
    assert "PROTECTED_OOS" in md or "protected" in md.lower()
    assert "UNPROVEN" in md
    assert "canonical executions authorized remains 0" in md.lower() or (
        "Canonical executions authorized remains 0" in md
    )
