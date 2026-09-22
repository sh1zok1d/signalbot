"""Synthetic tests for the D2 excess path-risk one-shot runner.

No real CORE BTC OHLC is loaded. No ADVERSE_SHARE / PATH_SCALE is
computed. ``EV.execute_decomposition`` is mocked for persist tests.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.research import d2_excess_path_risk_evaluator as EV
from scripts.research import d2_excess_path_risk_one_shot as OS
from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    CLASS_INVALID,
    CLASS_NO_STRUCTURE,
    file_sha256,
    verify_design_authorities,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_result_persistence import (
    canonical_result_bytes,
    result_payload_sha256,
)

REPO = Path(__file__).resolve().parents[2]
RUNNER_SRC = REPO / "scripts/research/d2_excess_path_risk_one_shot.py"
PERMIT_REL = EV.EXECUTION_PERMIT_REL
RESULT_JSON = OS.RESULT_JSON_REL
RESULT_MD = OS.RESULT_MD_REL

FROZEN_RUN_IDENTITY = OS.FROZEN_RUN_IDENTITY
FROZEN_DESIGN_JSON_SHA256 = OS.FROZEN_DESIGN_JSON_SHA256
FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256 = OS.FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256
FROZEN_REVIEWED_EVALUATOR_SHA256 = OS.FROZEN_REVIEWED_EVALUATOR_SHA256
FROZEN_SELECTOR_IDENTITY_AUTHORITY_SHA256 = (
    OS.FROZEN_SELECTOR_IDENTITY_AUTHORITY_SHA256
)
FROZEN_CANONICAL_SELECTOR_DIGEST = OS.FROZEN_CANONICAL_SELECTOR_DIGEST
FROZEN_CORE_BTC_SNAPSHOT_ID = OS.FROZEN_CORE_BTC_SNAPSHOT_ID

_COPY_RELS = (
    EV.EXECUTION_PERMIT_REL,
    EV.REVIEW_JSON_REL,
    EV.SELECTOR_IDENTITY_AUTHORITY_REL,
    "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.json",
    "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.md",
    "docs/research/discovery_results/D2_DISCOVERY_RESULT.json",
    "docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.json",
    C.CORE_BTC_SNAPSHOT_DOC_REL,
    *EV.IMPLEMENTATION_FILES,
)


def _copy_repo_tree(tmp_path: Path) -> Path:
    for rel in _COPY_RELS:
        src = REPO / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return tmp_path


def _synthetic_raw(**overrides):
    payload = {
        "UNIT": EV.UNIT,
        "CLASSIFICATION": CLASS_NO_STRUCTURE,
        "INTEGRITY_INVALID": False,
        "INTEGRITY_REASONS": [],
        "REAL_DECOMPOSITION_OUTCOME_COMPUTED": False,
        "MU_SHARE_RULE": 0.51,
        "DELTA_SHARE": 0.01,
        "RANDOM_SEED": 20260922131,
        "N_RANDOM_CONTROLS": 10000,
        "CANONICAL_SELECTOR_DIGEST": FROZEN_CANONICAL_SELECTOR_DIGEST,
    }
    payload.update(overrides)
    return payload


def test_permit_file_equals_tracked_expected_authority():
    stored = json.loads((REPO / PERMIT_REL).read_text(encoding="utf-8"))
    expected = EV.tracked_permit_expected_authority(REPO)
    assert stored == expected
    raw = (REPO / PERMIT_REL).read_text(encoding="utf-8")
    canonical = json.dumps(expected, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert raw == canonical


def test_verify_tracked_permit_passes_on_live_tree():
    stored = EV.verify_tracked_permit(REPO)
    assert stored["EXECUTION_AUTHORIZED"] is True
    assert stored["ONE_SHOT"] is True
    assert stored["RERUN_AUTHORIZED"] is False
    assert stored["RANDOM_SEED"] == 20260922131
    assert stored["N_RANDOM_CONTROLS"] == 10000
    assert stored["UNIT"] == EV.UNIT
    assert stored["RUN_IDENTITY"] == FROZEN_RUN_IDENTITY
    assert stored["DESIGN_JSON_SHA256"] == FROZEN_DESIGN_JSON_SHA256
    assert (
        stored["IMPLEMENTATION_REVIEW_JSON_SHA256"]
        == FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256
    )
    assert stored["REVIEWED_EVALUATOR_SHA256"] == FROZEN_REVIEWED_EVALUATOR_SHA256
    assert stored["CORE_BTC_SNAPSHOT_ID"] == FROZEN_CORE_BTC_SNAPSHOT_ID
    assert (
        stored["SELECTOR_IDENTITY_AUTHORITY_SHA256"]
        == FROZEN_SELECTOR_IDENTITY_AUTHORITY_SHA256
    )


def test_permit_binds_selector_and_review_identities():
    stored = EV.verify_tracked_permit(REPO)
    identity = EV.verify_selector_identity_authority(REPO)
    assert stored["SELECTOR_IDENTITY_AUTHORITY_SHA256"] == file_sha256(
        REPO / EV.SELECTOR_IDENTITY_AUTHORITY_REL
    )
    assert identity["CANONICAL_SELECTOR_DIGEST"] == FROZEN_CANONICAL_SELECTOR_DIGEST
    assert identity["RUN_IDENTITY"] == stored["RUN_IDENTITY"] == FROZEN_RUN_IDENTITY
    assert identity["DESIGN_JSON_SHA256"] == stored["DESIGN_JSON_SHA256"]
    assert identity["CORE_BTC_SNAPSHOT_ID"] == stored["CORE_BTC_SNAPSHOT_ID"]
    assert (
        identity["IMPLEMENTATION_REVIEW_JSON_SHA256"]
        == stored["IMPLEMENTATION_REVIEW_JSON_SHA256"]
    )
    assert EV.verify_core_btc_snapshot_identity(REPO) == FROZEN_CORE_BTC_SNAPSHOT_ID
    assert verify_design_authorities(REPO) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("DESIGN_JSON_SHA256", "0" * 64),
        ("IMPLEMENTATION_REVIEW_JSON_SHA256", "0" * 64),
        ("REVIEWED_EVALUATOR_SHA256", "0" * 64),
        ("CORE_BTC_SNAPSHOT_ID", "wrong-snapshot"),
        ("RUN_IDENTITY", "wrong-run-identity"),
        ("SELECTOR_IDENTITY_AUTHORITY_SHA256", "0" * 64),
        ("RANDOM_SEED", 1),
        ("N_RANDOM_CONTROLS", 1),
        ("UNIT", "WRONG_UNIT"),
        ("EXECUTION_AUTHORIZED", False),
        ("ONE_SHOT", False),
        ("RERUN_AUTHORIZED", True),
    ],
)
def test_mutated_permit_fails_verify(tmp_path, field, value):
    repo = _copy_repo_tree(tmp_path)
    path = repo / PERMIT_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(EV.PermitAuthorityError):
        EV.verify_tracked_permit(repo)


def test_malformed_permit_fails_verify(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    (repo / PERMIT_REL).write_text("{not-json", encoding="utf-8")
    with pytest.raises(EV.PermitAuthorityError, match="PERMIT_BYTES_UNPARSEABLE"):
        EV.verify_tracked_permit(repo)


def test_no_result_exists_in_permit_commit():
    assert not (REPO / RESULT_JSON).exists()
    assert not (REPO / RESULT_MD).exists()
    assert EV.EXECUTION_AUTHORIZED is False
    assert EV.frozen_contract_summary(REPO)["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is False


def test_runner_import_does_not_execute():
    source = RUNNER_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_calls = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            module_calls.append(node.value)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name in {
                "execute_one_shot",
                "execute_decomposition",
                "evaluate_decomposition",
                "canonical_orchestration",
                "build_target_rows",
            }:
                raise AssertionError(f"IMPORT_TIME_CALL:{name}")
    called = {"n": 0}

    def _boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("EXECUTE_DECOMPOSITION_AT_IMPORT")

    with patch.object(EV, "execute_decomposition", side_effect=_boom):
        importlib.reload(OS)
    assert called["n"] == 0
    assert "execute_one_shot" not in {
        getattr(n.value.func, "id", None) or getattr(n.value.func, "attr", None)
        for n in module_calls
        if isinstance(n, ast.Call)
    }


def test_runner_source_calls_execute_decomposition_once_and_not_evaluate():
    tree = ast.parse(RUNNER_SRC.read_text(encoding="utf-8"))
    execute_calls = 0
    forbidden = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name == "execute_decomposition":
            execute_calls += 1
        if name in {
            "evaluate_decomposition",
            "canonical_orchestration",
            "build_target_rows",
            "load_canonical_core_btc_bars",
            "load_core_btc_5m",
        }:
            forbidden.append(name)
    assert execute_calls == 1
    assert forbidden == []
    source = inspect.getsource(OS.execute_one_shot)
    assert "execute_decomposition(repo=" in source
    assert "evaluate_decomposition" not in source


def test_existing_result_blocks_rerun_before_execute(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    result = tmp_path / RESULT_JSON
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text("{}\n", encoding="utf-8")
    called = {"n": 0}

    def _boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("EXECUTE_DECOMPOSITION_CALLED")

    with patch.object(EV, "execute_decomposition", side_effect=_boom):
        with pytest.raises(OS.OneShotExecutionError, match="RESULT_ALREADY_EXISTS_RERUN_FORBIDDEN"):
            OS.execute_one_shot(repo=repo)
    assert called["n"] == 0


def test_existing_result_md_also_blocks_rerun(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    path = tmp_path / RESULT_MD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("already\n", encoding="utf-8")
    called = {"n": 0}

    def _boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("EXECUTE_DECOMPOSITION_CALLED")

    with patch.object(EV, "execute_decomposition", side_effect=_boom):
        with pytest.raises(OS.OneShotExecutionError, match="RESULT_ALREADY_EXISTS_RERUN_FORBIDDEN"):
            OS.execute_one_shot(repo=repo)
    assert called["n"] == 0


def test_authority_failure_does_not_fabricate_result(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    payload = json.loads((repo / PERMIT_REL).read_text(encoding="utf-8"))
    payload["RUN_IDENTITY"] = "forged"
    (repo / PERMIT_REL).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    called = {"n": 0}

    def _boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("EXECUTE_DECOMPOSITION_CALLED")

    with patch.object(EV, "execute_decomposition", side_effect=_boom):
        with pytest.raises(EV.PermitAuthorityError):
            OS.execute_one_shot(repo=repo)
    assert called["n"] == 0
    assert not (repo / RESULT_JSON).exists()
    assert not (repo / RESULT_MD).exists()


def test_execute_one_shot_calls_execute_decomposition_once(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    raw = _synthetic_raw()
    with patch.object(EV, "execute_decomposition", return_value=raw) as mocked:
        with patch.object(EV, "evaluate_decomposition") as eval_mock:
            written = OS.execute_one_shot(repo=repo)
    mocked.assert_called_once_with(repo=repo)
    eval_mock.assert_not_called()
    assert written["CLASSIFICATION"] == CLASS_NO_STRUCTURE
    assert written["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is True
    assert raw["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is False
    assert written["kind"] == "CANONICAL_ONE_SHOT_SCIENTIFIC_EXECUTION"
    assert written["ONE_SHOT"] is True
    assert written["EXECUTION_AUTHORIZED"] is True
    assert written["RERUN_AUTHORIZED"] is False
    assert written["PROTECTED_2025_OPENED"] is False
    assert written["PROTECTED_2026_OPENED"] is False
    assert written["BITMEX_2017_2019_REUSED_FOR_NEW_TARGET"] is False
    assert written["MARKET_07_CREATED"] is False
    assert written["CANONICAL_SELECTOR_DIGEST"] == FROZEN_CANONICAL_SELECTOR_DIGEST
    assert written["RUN_IDENTITY"] == FROZEN_RUN_IDENTITY
    assert written["DESIGN_JSON_SHA256"] == FROZEN_DESIGN_JSON_SHA256
    assert (
        written["IMPLEMENTATION_REVIEW_JSON_SHA256"]
        == FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256
    )
    assert written["REVIEWED_EVALUATOR_SHA256"] == FROZEN_REVIEWED_EVALUATOR_SHA256
    assert (
        written["SELECTOR_IDENTITY_AUTHORITY_SHA256"]
        == FROZEN_SELECTOR_IDENTITY_AUTHORITY_SHA256
    )
    assert written["EXECUTION_PERMIT_SHA256"] == file_sha256(repo / PERMIT_REL)
    assert written["PERMIT_COMMIT"]
    assert (repo / RESULT_JSON).is_file()
    assert (repo / RESULT_MD).is_file()


def test_classification_copied_without_reinterpretation(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    raw = _synthetic_raw(CLASSIFICATION="SYNTHETIC_UNREINTERPRETED_CLASS")
    with patch.object(EV, "execute_decomposition", return_value=raw):
        written = OS.execute_one_shot(repo=repo)
    assert written["CLASSIFICATION"] == "SYNTHETIC_UNREINTERPRETED_CLASS"


def test_invalid_classification_and_integrity_reasons_preserved(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    reasons = ["NO_TARGET_ELIGIBLE_CANDIDATE_ROWS"]
    raw = _synthetic_raw(
        CLASSIFICATION=CLASS_INVALID,
        INTEGRITY_INVALID=True,
        INTEGRITY_REASONS=list(reasons),
        MU_SHARE_RULE=None,
        DELTA_SHARE=None,
    )
    with patch.object(EV, "execute_decomposition", return_value=raw):
        written = OS.execute_one_shot(repo=repo)
    assert written["CLASSIFICATION"] == CLASS_INVALID
    assert written["INTEGRITY_INVALID"] is True
    assert written["INTEGRITY_REASONS"] == reasons
    assert written["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is True


def test_result_hash_is_deterministic(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    raw = _synthetic_raw()
    wrapped = OS.wrap_one_shot_result(
        raw,
        permit_commit="abc123",
        execution_permit_sha256="ab" * 32,
    )
    hashed = {k: v for k, v in wrapped.items() if k != "RESULT_PAYLOAD_SHA256"}
    digest_a = result_payload_sha256(hashed)
    digest_b = result_payload_sha256(dict(hashed))
    assert digest_a == digest_b
    assert len(digest_a) == 64
    with_hash = dict(hashed)
    with_hash["RESULT_PAYLOAD_SHA256"] = digest_a
    assert canonical_result_bytes(with_hash).endswith(b"\n")
    with patch.object(EV, "execute_decomposition", return_value=raw):
        written = OS.execute_one_shot(repo=repo)
    stored = json.loads((repo / RESULT_JSON).read_text(encoding="utf-8"))
    again = {k: v for k, v in stored.items() if k != "RESULT_PAYLOAD_SHA256"}
    assert stored["RESULT_PAYLOAD_SHA256"] == result_payload_sha256(again)
    assert written["RESULT_PAYLOAD_SHA256"] == stored["RESULT_PAYLOAD_SHA256"]


def test_second_invocation_refuses_before_execute(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    raw = _synthetic_raw()
    with patch.object(EV, "execute_decomposition", return_value=raw) as mocked:
        OS.execute_one_shot(repo=repo)
        with pytest.raises(OS.OneShotExecutionError, match="RESULT_ALREADY_EXISTS_RERUN_FORBIDDEN"):
            OS.execute_one_shot(repo=repo)
    assert mocked.call_count == 1


def test_exception_is_not_converted_to_scientific_class(tmp_path):
    repo = _copy_repo_tree(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("SYNTHETIC_EVALUATOR_CRASH")

    with patch.object(EV, "execute_decomposition", side_effect=_boom):
        with pytest.raises(RuntimeError, match="SYNTHETIC_EVALUATOR_CRASH"):
            OS.execute_one_shot(repo=repo)
    assert not (repo / RESULT_JSON).exists()
    assert not (repo / RESULT_MD).exists()


def test_missing_classification_fails_closed_without_result(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    raw = _synthetic_raw()
    del raw["CLASSIFICATION"]
    with patch.object(EV, "execute_decomposition", return_value=raw):
        with pytest.raises(OS.OneShotExecutionError, match="EVALUATOR_CLASSIFICATION_MISSING"):
            OS.execute_one_shot(repo=repo)
    assert not (repo / RESULT_JSON).exists()
