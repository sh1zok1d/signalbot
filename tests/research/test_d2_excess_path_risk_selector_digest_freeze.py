"""Tests for the pre-outcome D2 selector-identity digest freeze.

Verifies the tracked authority artifact. Does not load CORE BTC OHLC, does
not compute ADVERSE_SHARE / PATH_SCALE, and does not create a permit.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.research import d2_excess_path_risk_evaluator as EV
from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    FROZEN_D2_DISCOVERY_SHA256,
    FROZEN_RULE1_N,
    FROZEN_RULE1_YEAR_N,
    JSON_REL as DESIGN_JSON_REL,
    file_sha256,
    verify_design_authorities,
)
from scripts.research.d2_excess_path_risk_selector_digest_freeze import (
    EXPECTED_IMPLEMENTATION_COMMIT,
    EXPECTED_IMPLEMENTATION_TREE,
    EXPECTED_REVIEW_RUN_IDENTITY,
    FORBIDDEN_CALLS,
    UNIT as FREEZE_UNIT,
)
from scripts.research.discovery_sprint_01 import common as C

REPO = Path(__file__).resolve().parents[2]
FREEZE_SRC = REPO / "scripts/research/d2_excess_path_risk_selector_digest_freeze.py"
AUTHORITY_REL = EV.SELECTOR_IDENTITY_AUTHORITY_REL
FROZEN_AUTHORITY_SHA256 = (
    "a982b316254ba54c4974512e0b19fa122a37f1744c8b0c49b2666046f352d13c"
)
FROZEN_CANONICAL_SELECTOR_DIGEST = (
    "5eeb8480f8d1e576dec5e23f1a5545354c3d7b0fa16d76e6fbdbb89135b71f69"
)


def test_freeze_script_does_not_call_decomposition_surfaces():
    tree = ast.parse(FREEZE_SRC.read_text(encoding="utf-8"))
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name:
                called.add(name)
    for forbidden in FORBIDDEN_CALLS:
        assert forbidden not in called, f"FREEZE_CALLS_DECOMPOSITION:{forbidden}"


def test_selector_identity_authority_exists_and_verifies():
    path = REPO / AUTHORITY_REL
    assert path.is_file()
    stored = json.loads(path.read_text(encoding="utf-8"))
    verified = EV.verify_selector_identity_authority(REPO)
    assert verified == stored
    assert stored["UNIT"] == FREEZE_UNIT
    assert stored["KIND"] == "PRE_OUTCOME_SELECTOR_IDENTITY_AUTHORITY"
    assert stored["CANONICAL_SELECTOR_DIGEST_FROZEN"] is True
    assert stored["CANONICAL_SELECTOR_DIGEST"] == FROZEN_CANONICAL_SELECTOR_DIGEST
    assert len(stored["CANONICAL_SELECTOR_DIGEST"]) == 64
    assert stored["CANONICAL_SELECTOR_DIGEST"] == stored["CANONICAL_SELECTOR_DIGEST"].lower()
    assert stored["SELECTOR_DIGEST_ALGORITHM"] == "SHA256_ORDERED_T_MS_AND_SELECTOR_FLAGS_V1"
    assert stored["RUN_IDENTITY"] == EXPECTED_REVIEW_RUN_IDENTITY
    assert stored["CORE_BTC_SNAPSHOT_ID"] == C.CORE_BTC_SNAPSHOT
    assert stored["RULE_1_CONSTRUCTED_N"] == stored["RULE_1_N"] == 1791
    assert stored["SELECTOR_ABSTAIN_N"] == 163
    assert stored["RULE_1_N"] != stored["SELECTOR_ABSTAIN_N"]
    assert stored["RULE_1_N_MEANS_CONSTRUCTED_POPULATION"] is True
    assert stored["RULE_1_CONSTRUCTED_YEAR_N"] == dict(FROZEN_RULE1_YEAR_N)
    assert stored["SELECTOR_ABSTAIN_YEAR_N"] == dict(EV.FROZEN_SELECTOR_ABSTAIN_YEAR_N)
    assert stored["FROZEN_D2_DISCOVERY_SHA256"] == FROZEN_D2_DISCOVERY_SHA256


def test_selector_identity_authority_sha_is_stable():
    assert file_sha256(REPO / AUTHORITY_REL) == FROZEN_AUTHORITY_SHA256


def test_module_freeze_flag_remains_false_after_authority_exists():
    assert EV.CANONICAL_SELECTOR_DIGEST_FROZEN is False
    assert EV.EXECUTION_AUTHORIZED is False
    assert EV.EXECUTION_READY is False
    authority = json.loads((REPO / AUTHORITY_REL).read_text(encoding="utf-8"))
    assert authority["CANONICAL_SELECTOR_DIGEST_FROZEN"] is True


def test_no_execution_permit_or_result_created_by_the_freeze():
    # The freeze unit did not write RESULT or the permit. Later units may.
    freeze_src = FREEZE_SRC.read_text(encoding="utf-8")
    assert "D2_EXCESS_PATH_RISK_EXECUTION_PERMIT" not in freeze_src
    assert "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT" not in freeze_src


def test_frozen_implementation_and_design_bytes_unchanged():
    review = json.loads((REPO / EV.REVIEW_JSON_REL).read_text(encoding="utf-8"))
    assert review["FINAL_IMPLEMENTATION_COMMIT"] == EXPECTED_IMPLEMENTATION_COMMIT
    assert review["FINAL_IMPLEMENTATION_TREE"] == EXPECTED_IMPLEMENTATION_TREE
    assert review["RUN_IDENTITY"] == EXPECTED_REVIEW_RUN_IDENTITY
    assert review["CANONICAL_SELECTOR_DIGEST_FROZEN"] is False
    hashes = EV.current_implementation_file_sha256(REPO)
    assert hashes == review["IMPLEMENTATION_FILE_SHA256"]
    assert file_sha256(REPO / DESIGN_JSON_REL) == review["DESIGN_JSON_SHA256"]
    assert file_sha256(REPO / "docs/research/discovery_results/D2_DISCOVERY_RESULT.json") == (
        FROZEN_D2_DISCOVERY_SHA256
    )
    assert verify_design_authorities(REPO) == []
    facts = EV.verify_frozen_selector_identity_facts(REPO)
    assert facts["RULE_1_CONSTRUCTED_N"] == FROZEN_RULE1_N == 1791
    assert facts["SELECTOR_ABSTAIN_N"] == 163


def test_missing_authority_still_fails_closed(tmp_path):
    with pytest.raises(EV.PermitAuthorityError, match="SELECTOR_IDENTITY_AUTHORITY_MISSING"):
        EV.verify_selector_identity_authority(tmp_path)


def test_malformed_canonical_digest_fails_closed():
    stored = json.loads((REPO / AUTHORITY_REL).read_text(encoding="utf-8"))
    stored["CANONICAL_SELECTOR_DIGEST"] = "not-a-digest"
    with pytest.raises(EV.SelectorIdentityError, match="CANONICAL_DIGEST_MISSING"):
        EV.verify_selector_identity_authority_payload(
            stored,
            design_json_sha256=stored["DESIGN_JSON_SHA256"],
            implementation_review_json_sha256=stored["IMPLEMENTATION_REVIEW_JSON_SHA256"],
            run_identity=stored["RUN_IDENTITY"],
            core_btc_snapshot_id=stored["CORE_BTC_SNAPSHOT_ID"],
        )


def test_wrong_digest_fails_canonical_route_before_decomposition():
    authority = json.loads((REPO / AUTHORITY_REL).read_text(encoding="utf-8"))
    real_digest = authority["CANONICAL_SELECTOR_DIGEST"]
    wrong = "0" * 64
    assert real_digest != wrong
    authority["CANONICAL_SELECTOR_DIGEST"] = wrong
    called = {"eval": False}

    def _census(rows, mask):
        return {"SELECTOR_DIGEST": real_digest}

    def _boom(*args, **kwargs):
        called["eval"] = True
        raise AssertionError("EVALUATE_CALLED")

    rows, perp = _tiny_rows()
    with patch.object(EV, "verify_selector_identity", _census):
        with patch.object(EV, "evaluate_decomposition", _boom):
            with pytest.raises(EV.SelectorIdentityError, match="SELECTOR_DIGEST_NE_CANONICAL"):
                EV.canonical_orchestration(
                    load_core_bars=lambda: perp,
                    verify_core_snapshot=lambda: C.CORE_BTC_SNAPSHOT,
                    load_selector_identity_authority=lambda: authority,
                    build_rows_fn=lambda perp_map, start, end: rows,
                )
    assert called["eval"] is False


def _tiny_rows():
    from scripts.research.discovery_sprint_01 import common as C

    row = C.DiscoveryRow(
        t_ms=int(C.ms_from_utc(C.RULE1_INTERVAL_START)),
        year=2020,
        rv=1.0,
        ret=0.01,
        side=1.0,
        severity=0.02,
        entry_open=100.0,
        future_closes=tuple(100.0 for _ in range(288)),
    )
    return [row], {}
