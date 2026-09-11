"""Bounded contract tests for the performance/execution freeze.

Docs/metadata-only. Does not execute the 3200-world grid, create an ARM,
consume authority, or mint RESULT/WORLD_RECORDS. Does not import or run
scientific evaluation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FREEZE_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PERFORMANCE_EXECUTION_FREEZE.json"
)
REVIEWED_HEAD = "9c573df81dad55829f52cff0f94e8c5918c30fd9"
REVIEWED_TREE = "b9d928687e5ea4e9773f07b0cb6f8e287b65562f"
OLD_ARM = "0abc5fe167e018ebe1f7efbb70694887ac095e17"
LIB_SHA256 = "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
WORKER_SHA256 = "9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e"
WORKER_SIZE = 3994
PREREG_JSON_SHA256 = "78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708"
PREREG_MD_SHA256 = "a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3"
PREREG_JSON_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
PREREG_MD_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
TCB_PATHS = (
    "scripts/research/harness_synthetic_edge_calibration_v1_lib.py",
    "scripts/research/harness_synthetic_edge_calibration_v1.py",
    "scripts/research/harness_synthetic_edge_calibration_v1_auth.py",
    "scripts/research/harness_synthetic_edge_calibration_v1_production.py",
    "scripts/research/harness_synthetic_edge_calibration_v1_worker.py",
)
UNSET = "UNSET_UNTIL_THIS_COMMIT"
FALSE_FLAGS = (
    "production_executed",
    "production_calibration_executed",
    "authorization_consumed",
    "result_created",
    "production_result_minted",
    "world_records_created",
    "world_records_persisted",
    "production_armed",
    "production_monte_carlo_arm_authorized",
    "B2_06_scientific_execution_authorized",
    "validation_2025_authorized",
    "oos_2026_authorized",
    "real_market_data_access_authorized",
    "other_hypothesis_authorized",
    "claim_depends_on_prior_auth_proof",
)
TRUE_FLAGS = (
    "freeze_docs_only",
    "not_a_result",
    "scientific_plan_unchanged",
    "checkpoint_is_untrusted_cache",
    "isolated_frozen_git_authentication_required_before_mint",
    "claim_time_historical_recomputation_independent",
    "auth_and_claim_trust_roles_distinct",
    "verifier_paths_world_parallel",
    "canonical_reorder_required",
    "worker_count_operational_not_scientific",
    "rng_invariant_under_worker_count",
    "exact_output_invariant_under_worker_count",
)


class FreezeContractError(ValueError):
    """Performance execution freeze artifact failed closed."""


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(REPO), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise FreezeContractError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _blob(commit: str, rel: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "blob", f"{commit}:{rel}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise FreezeContractError(f"missing git object {commit}:{rel}")
    return proc.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_freeze() -> dict:
    path = REPO / FREEZE_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FreezeContractError("freeze artifact is not an object")
    return payload


def validate_performance_execution_freeze(payload: object) -> None:
    """Fail closed unless the freeze artifact binds the reviewed implementation."""
    if not isinstance(payload, dict):
        raise FreezeContractError("freeze artifact is not an object")
    if payload.get("schema_version") != "1.0":
        raise FreezeContractError("schema_version is not 1.0")
    if payload.get("unit_id") != "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1":
        raise FreezeContractError("unit_id mismatch")
    if payload.get("freeze_purpose") != "PERFORMANCE_EXECUTION_FREEZE":
        raise FreezeContractError("freeze_purpose mismatch")
    if payload.get("freeze_status") != "PERFORMANCE_EXECUTION_FROZEN_UNARMED":
        raise FreezeContractError("freeze_status mismatch")
    if payload.get("canonical_path") != FREEZE_REL:
        raise FreezeContractError("canonical_path mismatch")
    if payload.get("reviewed_implementation_head") != REVIEWED_HEAD:
        raise FreezeContractError("reviewed_implementation_head mismatch")
    if payload.get("reviewed_implementation_tree") != REVIEWED_TREE:
        raise FreezeContractError("reviewed_implementation_tree mismatch")
    if payload.get("freeze_commit_head") != UNSET:
        raise FreezeContractError("freeze_commit_head must remain unset until this commit")
    if payload.get("freeze_commit_tree") != UNSET:
        raise FreezeContractError("freeze_commit_tree must remain unset until this commit")
    if payload.get("opus_blockers") != 0:
        raise FreezeContractError("opus_blockers is not 0")
    if payload.get("opus_majors") != 0:
        raise FreezeContractError("opus_majors is not 0")
    if payload.get("opus_minors") != 0:
        raise FreezeContractError("opus_minors is not 0")
    if payload.get("opus_closure") != "GO_FOR_PERFORMANCE_FREEZE":
        raise FreezeContractError("opus_closure mismatch")
    findings = payload.get("closed_findings")
    if not isinstance(findings, dict):
        raise FreezeContractError("closed_findings missing")
    for key in ("BLOCKER-1", "MAJOR-1", "BLOCKER-2"):
        if findings.get(key) != "CLOSED":
            raise FreezeContractError(f"{key} is not CLOSED")
    if payload.get("frozen_lib_sha256") != LIB_SHA256:
        raise FreezeContractError("frozen_lib_sha256 mismatch")
    if payload.get("prereg_json_sha256") != PREREG_JSON_SHA256:
        raise FreezeContractError("prereg_json_sha256 mismatch")
    if payload.get("prereg_md_sha256") != PREREG_MD_SHA256:
        raise FreezeContractError("prereg_md_sha256 mismatch")
    old_arm = payload.get("old_arm")
    if not isinstance(old_arm, dict):
        raise FreezeContractError("old_arm missing")
    if old_arm.get("commit") != OLD_ARM:
        raise FreezeContractError("old_arm commit mismatch")
    if "DOES_NOT_AUTHORIZE_THIS_IMPLEMENTATION" not in str(old_arm.get("status") or ""):
        raise FreezeContractError("old_arm status does not refuse this implementation")
    for key in FALSE_FLAGS:
        if payload.get(key) is not False:
            raise FreezeContractError(f"{key} must be false")
    for key in TRUE_FLAGS:
        if payload.get(key) is not True:
            raise FreezeContractError(f"{key} must be true")
    measured = payload.get("measured_performance")
    if not isinstance(measured, dict) or measured.get("class") != "MEASURED":
        raise FreezeContractError("measured_performance.class is not MEASURED")
    if measured.get("n5000_1w_seconds_per_world") != 5.6371:
        raise FreezeContractError("n5000 1W measurement mismatch")
    if measured.get("n5000_2w_seconds_per_world") != 3.0444:
        raise FreezeContractError("n5000 2W measurement mismatch")
    if measured.get("n5000_4w_seconds_per_world") != 1.5149:
        raise FreezeContractError("n5000 4W measurement mismatch")
    if measured.get("n5000_4w_speedup_vs_1w") != 3.72:
        raise FreezeContractError("n5000 4W speedup mismatch")
    extrapolated = payload.get("extrapolated_lifecycle_not_measured")
    if not isinstance(extrapolated, dict) or extrapolated.get("class") != "EXTRAPOLATED":
        raise FreezeContractError("8W/16W lifecycle is not labeled EXTRAPOLATED")
    tcb = payload.get("execution_tcb")
    if not isinstance(tcb, list) or len(tcb) != len(TCB_PATHS):
        raise FreezeContractError("execution_tcb is not the complete TCB list")
    seen: list[str] = []
    for row, expected_path in zip(tcb, TCB_PATHS, strict=True):
        if not isinstance(row, dict):
            raise FreezeContractError("execution_tcb row is not an object")
        path = row.get("path")
        digest = row.get("sha256")
        size = row.get("size")
        if path != expected_path:
            raise FreezeContractError("execution_tcb path mismatch")
        if not isinstance(digest, str) or len(digest) != 64:
            raise FreezeContractError("execution_tcb sha256 is malformed")
        if type(size) is not int or size < 1:
            raise FreezeContractError("execution_tcb size is not a positive int")
        blob = _blob(REVIEWED_HEAD, expected_path)
        if _sha256(blob) != digest:
            raise FreezeContractError(f"execution_tcb sha256 does not match git object: {path}")
        if len(blob) != size:
            raise FreezeContractError(f"execution_tcb size does not match git object: {path}")
        seen.append(expected_path)
    if tuple(seen) != TCB_PATHS:
        raise FreezeContractError("execution_tcb path order/completeness mismatch")
    worker = tcb[4]
    if worker["sha256"] != WORKER_SHA256 or worker["size"] != WORKER_SIZE:
        raise FreezeContractError("worker git-object identity mismatch")
    if tcb[0]["sha256"] != LIB_SHA256:
        raise FreezeContractError("lib git-object identity mismatch")
    if _sha256(_blob(REVIEWED_HEAD, PREREG_JSON_REL)) != payload["prereg_json_sha256"]:
        raise FreezeContractError("prereg JSON does not match reviewed git object")
    if _sha256(_blob(REVIEWED_HEAD, PREREG_MD_REL)) != payload["prereg_md_sha256"]:
        raise FreezeContractError("prereg MD does not match reviewed git object")
    if _git("rev-parse", f"{REVIEWED_HEAD}^{{tree}}") != REVIEWED_TREE:
        raise FreezeContractError("reviewed implementation tree does not match git")


def test_freeze_artifact_binds_reviewed_git_objects():
    validate_performance_execution_freeze(_load_freeze())


def test_freeze_artifact_is_canonical_json():
    raw = (REPO / FREEZE_REL).read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    expected = (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    assert raw == expected


def test_reviewed_tcb_unchanged_on_live_head():
    head = _git("rev-parse", "HEAD")
    ancestor = subprocess.run(
        ["git", "-C", str(REPO), "merge-base", "--is-ancestor", REVIEWED_HEAD, head],
        check=False,
    )
    assert ancestor.returncode == 0
    assert _git("rev-parse", f"{REVIEWED_HEAD}^{{tree}}") == REVIEWED_TREE
    freeze_head = "ccaffe135c2b8a9a0a75af30c0712ba3063b82f6"
    arm_head = "120ac456df3a22884c48eed45852bdd001706f54"
    for rel in TCB_PATHS + (PREREG_JSON_REL, PREREG_MD_REL):
        assert _blob(freeze_head, rel) == _blob(REVIEWED_HEAD, rel)
        assert _blob(arm_head, rel) == _blob(REVIEWED_HEAD, rel)
    if head in {REVIEWED_HEAD, freeze_head, arm_head}:
        for rel in TCB_PATHS + (PREREG_JSON_REL, PREREG_MD_REL):
            assert _blob(head, rel) == _blob(REVIEWED_HEAD, rel)


def test_freeze_does_not_embed_own_commit_identity():
    payload = _load_freeze()
    assert payload["freeze_commit_head"] == UNSET
    assert payload["freeze_commit_tree"] == UNSET
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    dumped = json.dumps(payload)
    assert head not in dumped or head == REVIEWED_HEAD
    assert tree not in dumped or tree == REVIEWED_TREE


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda p: p.__setitem__("reviewed_implementation_head", "0" * 40), "reviewed_implementation_head"),
        (lambda p: p.__setitem__("reviewed_implementation_tree", "1" * 40), "reviewed_implementation_tree"),
        (lambda p: p["execution_tcb"][4].__setitem__("sha256", "a" * 64), "sha256"),
        (lambda p: p["execution_tcb"][3].__setitem__("sha256", "b" * 64), "sha256"),
        (lambda p: p.__setitem__("frozen_lib_sha256", "c" * 64), "frozen_lib_sha256"),
        (lambda p: p["execution_tcb"][4].__setitem__("size", 1), "size"),
        (
            lambda p: p["execution_tcb"][4].__setitem__(
                "path", "scripts/research/harness_synthetic_edge_calibration_v1_performance.py"
            ),
            "path",
        ),
        (lambda p: p.__setitem__("prereg_json_sha256", "d" * 64), "prereg"),
        (lambda p: p.__setitem__("opus_closure", "NO"), "opus_closure"),
        (lambda p: p.__setitem__("opus_blockers", 1), "opus_blockers"),
        (lambda p: p.__setitem__("opus_majors", 1), "opus_majors"),
        (lambda p: p.__setitem__("opus_minors", 1), "opus_minors"),
        (lambda p: p["closed_findings"].__setitem__("BLOCKER-2", "OPEN"), "BLOCKER-2"),
        (lambda p: p.__setitem__("production_armed", True), "production_armed"),
        (lambda p: p.__setitem__("production_executed", True), "production_executed"),
    ],
    ids=[
        "wrong_head",
        "wrong_tree",
        "wrong_worker_digest",
        "wrong_production_digest",
        "wrong_lib_digest",
        "wrong_size",
        "wrong_path",
        "wrong_prereg_digest",
        "wrong_verdict_closure",
        "wrong_blockers",
        "wrong_majors",
        "wrong_minors",
        "wrong_closed_finding",
        "armed",
        "executed",
    ],
)
def test_tampered_freeze_contract_refused(mutator, match):
    payload = copy.deepcopy(_load_freeze())
    mutator(payload)
    with pytest.raises(FreezeContractError, match=match):
        validate_performance_execution_freeze(payload)


def test_old_arm_does_not_authorize_reviewed_performance_head():
    from scripts.research import harness_synthetic_edge_calibration_v1_production as prod

    arm = json.loads(_blob(OLD_ARM, prod.CANONICAL_ARM_PATH).decode("utf-8"))
    assert prod._arm_payload_authorizes_at_commit(REPO, REVIEWED_HEAD, arm) is False
    live = _git("rev-parse", "HEAD")
    assert prod._arm_payload_authorizes_at_commit(REPO, live, arm) is False
    assert prod.production_monte_carlo_arm_authorized() is False
