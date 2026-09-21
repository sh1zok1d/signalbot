"""MARKET-03 implementation freeze identity checks.

Does not execute MARKET-03, inspect outcomes, ARM, or change scientific
implementation bytes. Binds the freeze record to the reviewed HEAD.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FREEZE_MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE.md"
FREEZE_JSON = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE.json"
PREREG_MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
PREREG_JSON = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
LIB = REPO / "scripts/research/market_03_public_strategy_lib.py"
AUTHORITY = REPO / "scripts/research/market_03_public_strategy_authority.py"
EXECUTE = REPO / "scripts/research/market_03_public_strategy_execute.py"

REVIEWED_HEAD = "03411aaa1a2f938169f07f8f3576f17227a2b14b"
REVIEWED_TREE = "87a1da250a56343c44625e3f5187a6877035d1da"

EXPECTED = {
    "scripts/research/market_03_public_strategy_lib.py": {
        "sha256": "46ec2449e967172b61eec32f5ab6caf897ff9db04249395ac55a2368840289a5",
        "git_blob": "979f9e735163cf53a265a4e8c3dc93ba37f8b20e",
        "size_bytes": 38012,
    },
    "scripts/research/market_03_public_strategy_authority.py": {
        "sha256": "97f000c6afc2427db9fe3f90548f77c7e7ab4da0e43ba3283159101565a305e4",
        "git_blob": "bb922ee9755e911dabf6ead1250ea1295ffa162e",
        "size_bytes": 13235,
    },
    "scripts/research/market_03_public_strategy_execute.py": {
        "sha256": "90fd315d926b2b957391ed31c71bff6a33b0f22257960d0779e27e277cb40bcf",
        "git_blob": "7d04ae75651060c52bea8e7ae848c6f97b6233dd",
        "size_bytes": 1292,
    },
}
PREREG_MD_SHA = "044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57"
PREREG_JSON_SHA = "3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _blob(rel: str) -> str:
    return subprocess.check_output(["git", "hash-object", str(REPO / rel)], text=True).strip()


def _freeze() -> dict:
    return json.loads(FREEZE_JSON.read_text(encoding="utf-8"))


def test_freeze_binds_reviewed_head_tree_and_unsets_self_hash():
    freeze = _freeze()
    assert freeze["status"] == "IMPLEMENTATION_FROZEN"
    assert freeze["reviewed_implementation"]["head"] == REVIEWED_HEAD
    assert freeze["reviewed_implementation"]["tree"] == REVIEWED_TREE
    assert freeze["re_review"]["verdict"] == "READY_FOR_IMPLEMENTATION_FREEZE"
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"
    md = FREEZE_MD.read_text(encoding="utf-8")
    assert REVIEWED_HEAD in md
    assert REVIEWED_TREE in md
    assert "IMPLEMENTATION_FROZEN                = YES" in md
    assert "MARKET_03_ARMED                      = NO" in md


def test_freeze_locks_scientific_bytes_to_reviewed_identity():
    freeze = _freeze()
    files = freeze["frozen_scientific_implementation"]
    for rel, expected in EXPECTED.items():
        meta = files[rel]
        path = REPO / rel
        assert _sha256(path) == expected["sha256"]
        assert meta["sha256"] == expected["sha256"]
        assert path.stat().st_size == expected["size_bytes"]
        assert meta["size_bytes"] == expected["size_bytes"]
        assert _blob(rel) == expected["git_blob"]
        reviewed = subprocess.check_output(
            ["git", "show", f"{REVIEWED_HEAD}:{rel}"],
            cwd=REPO,
        )
        assert hashlib.sha256(reviewed).hexdigest() == expected["sha256"]
        assert reviewed == path.read_bytes()


def test_freeze_locks_prereg_and_data_authorities():
    freeze = _freeze()
    assert _sha256(PREREG_MD) == PREREG_MD_SHA
    assert _sha256(PREREG_JSON) == PREREG_JSON_SHA
    assert freeze["prereg"]["md_sha256"] == PREREG_MD_SHA
    assert freeze["prereg"]["json_sha256"] == PREREG_JSON_SHA
    assert freeze["prereg"]["changed"] is False
    src = freeze["pinned_external_source"]
    assert src["commit"] == "b68a5518b4a3eba2fde1733160d7d7de356023b5"
    assert src["tree"] == "f7717e681c911ea3ccce15492246053cf15883cb"
    spot = freeze["data_authorities"]["spot"]
    assert spot["snapshot_id"] == "2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345"
    assert spot["data_sha256"] == "e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4"
    fund = freeze["data_authorities"]["funding"]
    assert fund["snapshot_id"] == "d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68"
    assert fund["data_sha256"] == "e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb"
    assert fund["b2_06_is_not_authority"] is True
    assert freeze["intervals"]["warmup_start_inclusive"] == "2019-08-07T20:00:00Z"
    assert freeze["intervals"]["evaluation_end_exclusive"] == "2025-01-01T00:00:00Z"


def test_freeze_preserves_primary_rule_partial_differential_and_unarmed_execution():
    freeze = _freeze()
    assert "MDD_filtered > MDD_baseline" in freeze["primary_classification"]["equation"]
    assert freeze["fidelity"]["EXACT_DIFFERENTIAL_TESTS"] == "PARTIAL"
    assert freeze["fundingTime_assumption"]["STRICT_HISTORICAL_PUBLICATION_LATENCY"] == "UNPROVEN"
    assert freeze["tests_at_review"]["FULL_PYTEST_AT_REVIEW"] == "NOT_COMPLETED"
    state = freeze["explicit_state"]
    assert state["IMPLEMENTATION_FROZEN"] is True
    assert state["MARKET_03_ARMED"] is False
    assert state["CANONICAL_EXECUTIONS_AUTHORIZED"] == 0
    assert state["CANONICAL_EXECUTIONS_CONSUMED"] == 0
    assert state["MARKET_03_STRATEGY_EXECUTED"] is False
    assert state["MARKET_03_OUTCOMES_INSPECTED"] is False
    assert state["PROTECTED_OOS_TOUCHED"] is False
    assert freeze["not_an_arm"] is True
    assert freeze["next_lifecycle_state"] == "MARKET-03_ARM"
    closures = freeze["review_closures"]
    assert closures["F1_CLOSED"] is True
    assert closures["F2_CLOSED"] is True
    assert closures["F3_CLOSED"] is True
    assert closures["F5_CLOSED"] is True
    assert closures["F1_REPRODUCIBLE_AFTER_REPAIR"] is False
    from scripts.research.market_03_public_strategy_authority import (
        IMPLEMENTATION_FROZEN,
        MARKET_03_ARMED,
        MARKET_03_BOUND_EXECUTION_AUTHORIZED,
        CANONICAL_EXECUTIONS_AUTHORIZED,
    )

    # Reviewed code identity remains unarmed; freeze is documentary authority.
    assert IMPLEMENTATION_FROZEN is False
    assert MARKET_03_ARMED is False
    assert MARKET_03_BOUND_EXECUTION_AUTHORIZED is False
    assert CANONICAL_EXECUTIONS_AUTHORIZED == 0
