"""ARM contract for the performance/execution freeze parent.

Docs/authority-artifact only. Does not start canonical production, mint
RESULT/WORLD_RECORDS, create a reservation/claim, or consume authority.
Does not modify the unused driver ARM git object at 0abc5fe.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_production as prod

REPO = Path(__file__).resolve().parents[2]
ARM_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json"
FREEZE_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PERFORMANCE_EXECUTION_FREEZE.json"
)
REVIEWED_HEAD = "9c573df81dad55829f52cff0f94e8c5918c30fd9"
REVIEWED_TREE = "b9d928687e5ea4e9773f07b0cb6f8e287b65562f"
FREEZE_HEAD = "ccaffe135c2b8a9a0a75af30c0712ba3063b82f6"
FREEZE_TREE = "ea012c70f83346abe6064b33e5f29987278c268e"
FREEZE_SHA256 = "2df563ad097cbaafcf4707146166ee6acf33776acc5e60c0e5c15df3428b6c54"
FREEZE_SIZE = 4552
OLD_ARM = "0abc5fe167e018ebe1f7efbb70694887ac095e17"
PLAN_SHA256 = "5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6"
LIB_SHA256 = "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
RUNNER_SHA256 = "0a5e577cc3797b018e9912865b7c3e385908764dc6cb36a6555626205855432a"
AUTH_SHA256 = "0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507"
PRODUCTION_SHA256 = "67773bf770cb84e317b6ea640c86c0863ba31c44e0d1dcdb2e47da66bceda4a5"
WORKER_SHA256 = "9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e"
WORKER_SIZE = 3994
PREREG_JSON_SHA256 = "78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708"
PREREG_MD_SHA256 = "a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3"
TCB = (
    ("lib", "scripts/research/harness_synthetic_edge_calibration_v1_lib.py", LIB_SHA256),
    ("runner", "scripts/research/harness_synthetic_edge_calibration_v1.py", RUNNER_SHA256),
    ("auth", "scripts/research/harness_synthetic_edge_calibration_v1_auth.py", AUTH_SHA256),
    (
        "production",
        "scripts/research/harness_synthetic_edge_calibration_v1_production.py",
        PRODUCTION_SHA256,
    ),
    ("worker", "scripts/research/harness_synthetic_edge_calibration_v1_worker.py", WORKER_SHA256),
)


class ArmContractError(ValueError):
    """Performance production ARM artifact failed closed."""


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(REPO), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise ArmContractError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _blob(commit: str, rel: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "blob", f"{commit}:{rel}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ArmContractError(f"missing git object {commit}:{rel}")
    return proc.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_arm() -> dict:
    payload = json.loads((REPO / ARM_REL).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ArmContractError("ARM artifact is not an object")
    return payload


def validate_performance_production_arm(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ArmContractError("ARM artifact is not an object")
    freeze_blob = _blob(FREEZE_HEAD, FREEZE_REL)
    if _sha256(freeze_blob) != FREEZE_SHA256 or len(freeze_blob) != FREEZE_SIZE:
        raise ArmContractError("freeze artifact SHA/size mismatch")
    freeze = json.loads(freeze_blob.decode("utf-8"))
    if payload.get("schema_version") != "1.0":
        raise ArmContractError("schema_version is not 1.0")
    if payload.get("canonical_path") != ARM_REL:
        raise ArmContractError("canonical_path mismatch")
    if payload.get("freeze_parent_head") != FREEZE_HEAD:
        raise ArmContractError("wrong freeze parent")
    if payload.get("freeze_parent_tree") != FREEZE_TREE:
        raise ArmContractError("wrong freeze parent tree")
    if payload.get("authorized_execution_commit") != FREEZE_HEAD:
        raise ArmContractError("wrong freeze parent")
    if payload.get("authorized_execution_tree") != FREEZE_TREE:
        raise ArmContractError("wrong freeze parent tree")
    if payload.get("reviewed_implementation_head") != REVIEWED_HEAD:
        raise ArmContractError("wrong reviewed implementation HEAD")
    if payload.get("reviewed_implementation_tree") != REVIEWED_TREE:
        raise ArmContractError("wrong reviewed implementation TREE")
    if payload.get("freeze_artifact_path") != FREEZE_REL:
        raise ArmContractError("wrong freeze artifact path")
    if payload.get("freeze_artifact_sha256") != FREEZE_SHA256:
        raise ArmContractError("wrong freeze artifact SHA")
    if payload.get("freeze_artifact_size") != FREEZE_SIZE:
        raise ArmContractError("wrong freeze artifact size")
    if freeze.get("reviewed_implementation_head") != REVIEWED_HEAD:
        raise ArmContractError("freeze reviewed HEAD mismatch")
    if freeze.get("reviewed_implementation_tree") != REVIEWED_TREE:
        raise ArmContractError("freeze reviewed TREE mismatch")
    if payload.get("frozen_lib_sha256") != LIB_SHA256:
        raise ArmContractError("wrong lib hash")
    listed = payload.get("execution_authority_sha256")
    if not isinstance(listed, dict):
        raise ArmContractError("execution_authority_sha256 missing")
    if listed.get("lib") != LIB_SHA256:
        raise ArmContractError("wrong lib hash")
    if listed.get("runner") != RUNNER_SHA256:
        raise ArmContractError("wrong runner hash")
    if listed.get("auth") != AUTH_SHA256:
        raise ArmContractError("wrong auth hash")
    if listed.get("production") != PRODUCTION_SHA256:
        raise ArmContractError("wrong production hash")
    if listed.get("worker") != WORKER_SHA256:
        raise ArmContractError("wrong worker hash")
    if listed.get("prereg_json") != PREREG_JSON_SHA256:
        raise ArmContractError("wrong prereg hashes")
    if listed.get("prereg_md") != PREREG_MD_SHA256:
        raise ArmContractError("wrong prereg hashes")
    if payload.get("prereg_json_sha256") != PREREG_JSON_SHA256:
        raise ArmContractError("wrong prereg hashes")
    if payload.get("prereg_md_sha256") != PREREG_MD_SHA256:
        raise ArmContractError("wrong prereg hashes")
    tcb = payload.get("execution_tcb")
    if not isinstance(tcb, list) or len(tcb) != 5:
        raise ArmContractError("execution TCB does not match freeze artifact")
    worker = tcb[4]
    if not isinstance(worker, dict):
        raise ArmContractError("wrong worker hash/size")
    if worker.get("sha256") != WORKER_SHA256 or worker.get("size") != WORKER_SIZE:
        raise ArmContractError("wrong worker hash/size")
    freeze_tcb = freeze.get("execution_tcb")
    if tcb != freeze_tcb:
        raise ArmContractError("execution TCB does not match freeze artifact")
    actual = prod._authority_digests_at(REPO, FREEZE_HEAD)
    for key, rel, digest in TCB:
        blob = _blob(FREEZE_HEAD, rel)
        if _sha256(blob) != digest or listed.get(key) != actual.get(key):
            raise ArmContractError(f"wrong {key} hash")
        if key == "worker" and len(blob) != WORKER_SIZE:
            raise ArmContractError("wrong worker hash/size")
    if payload.get("authorized_plan_sha256") != PLAN_SHA256:
        raise ArmContractError("wrong frozen plan identity")
    if payload.get("authorized_grid") != prod.frozen_production_grid():
        raise ArmContractError("wrong frozen plan identity")
    if payload.get("authorized_plan") != "exact_frozen_3200_world_plan":
        raise ArmContractError("wrong frozen plan identity")
    if prod.planned_jobs_sha256(prod.planned_production_jobs()) != PLAN_SHA256:
        raise ArmContractError("wrong frozen plan identity")
    if payload.get("production_monte_carlo_arm_authorized") is not True:
        raise ArmContractError("ARM must declare production_monte_carlo_arm_authorized")
    if payload.get("authorization_consumed") is not False:
        raise ArmContractError("protected state already consumed")
    if payload.get("production_executed") is not False:
        raise ArmContractError("production already executed")
    if payload.get("production_calibration_executed") is not False:
        raise ArmContractError("production already executed")
    if payload.get("production_result_minted") is not False:
        raise ArmContractError("RESULT already present")
    if payload.get("result_created") is not False:
        raise ArmContractError("RESULT already present")
    if payload.get("world_records_persisted") is not False:
        raise ArmContractError("WORLD_RECORDS already present")
    if payload.get("world_records_created") is not False:
        raise ArmContractError("WORLD_RECORDS already present")
    if payload.get("worker_count_is_operational") is not True:
        raise ArmContractError("worker count must be operational")
    if payload.get("worker_count_changes_science") is not False:
        raise ArmContractError("worker count must not change science")
    if payload.get("not_a_result") is not True or payload.get("not_an_execution") is not True:
        raise ArmContractError("ARM must not contain results or execute science")
    if (REPO / prod.CANONICAL_RESULT_PATH).exists():
        raise ArmContractError("RESULT already present")
    if (REPO / prod.CANONICAL_WORLD_RECORDS_PATH).exists():
        raise ArmContractError("WORLD_RECORDS already present")
    if (REPO / prod.CANONICAL_RESERVATION_PATH).exists():
        raise ArmContractError("protected state already consumed")
    if (REPO / prod.CANONICAL_CLAIM_PATH).exists():
        raise ArmContractError("protected state already consumed")
    for key, expected in prod.ARM_REQUIRED_LITERALS.items():
        if payload.get(key) != expected:
            raise ArmContractError(f"ARM required literal mismatch: {key}")
    old = payload.get("superseded_unused_arm_0abc5fe")
    if not isinstance(old, dict) or old.get("head") != OLD_ARM:
        raise ArmContractError("superseded/old ARM missing")
    if "DOES_NOT_AUTHORIZE_THIS_IMPLEMENTATION" not in str(old.get("status") or ""):
        raise ArmContractError("superseded/old ARM")


def validate_arm_commit_topology(commit: str, payload: object) -> None:
    validate_performance_production_arm(payload)
    parent = _git("rev-parse", f"{commit}^")
    if parent != FREEZE_HEAD:
        raise ArmContractError("non-immediate child")
    count = _git("rev-list", "--count", f"{FREEZE_HEAD}..{commit}")
    if count != "1":
        raise ArmContractError("non-immediate child")
    for _key, rel, _digest in TCB:
        if _blob(commit, rel) != _blob(FREEZE_HEAD, rel):
            raise ArmContractError("execution TCB does not match freeze artifact")
    if _blob(commit, FREEZE_REL) != _blob(FREEZE_HEAD, FREEZE_REL):
        raise ArmContractError("wrong freeze artifact SHA")


def test_arm_artifact_binds_performance_freeze_git_objects():
    validate_performance_production_arm(_load_arm())


def test_arm_artifact_is_canonical_json():
    raw = (REPO / ARM_REL).read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    expected = (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    assert raw == expected


def test_arm_is_immediate_child_of_freeze_when_committed():
    arm_commit = "120ac456df3a22884c48eed45852bdd001706f54"
    payload = json.loads(_blob(arm_commit, ARM_REL).decode("utf-8"))
    validate_arm_commit_topology(arm_commit, payload)
    head = _git("rev-parse", "HEAD")
    if head != arm_commit and head != FREEZE_HEAD:
        with pytest.raises(ArmContractError, match="non-immediate child"):
            validate_arm_commit_topology(head, payload)


def test_non_immediate_child_and_wrong_commits_refused():
    arm = _load_arm()
    with pytest.raises(ArmContractError, match="non-immediate child"):
        validate_arm_commit_topology(FREEZE_HEAD, arm)
    with pytest.raises(ArmContractError, match="non-immediate child"):
        validate_arm_commit_topology(OLD_ARM, arm)
    with pytest.raises(ArmContractError, match="non-immediate child"):
        validate_arm_commit_topology(REVIEWED_HEAD, arm)


def test_no_canonical_production_artifacts_or_consumption():
    arm = _load_arm()
    assert arm["authorization_consumed"] is False
    assert arm["production_executed"] is False
    assert (REPO / prod.CANONICAL_RESULT_PATH).exists() is False
    assert (REPO / prod.CANONICAL_WORLD_RECORDS_PATH).exists() is False
    assert (REPO / prod.CANONICAL_RESERVATION_PATH).exists() is False
    assert (REPO / prod.CANONICAL_CLAIM_PATH).exists() is False
    assert (REPO / prod.CANONICAL_PARTIAL_PATH).exists() is False


def test_old_arm_does_not_authorize_freeze_or_live_head():
    old = json.loads(_blob(OLD_ARM, ARM_REL).decode("utf-8"))
    assert prod._arm_payload_authorizes_at_commit(REPO, OLD_ARM, old) is False
    assert prod._arm_payload_authorizes_at_commit(REPO, FREEZE_HEAD, old) is False
    live = _git("rev-parse", "HEAD")
    if live != OLD_ARM:
        assert prod._arm_payload_authorizes_at_commit(REPO, live, old) is False


def test_repaired_runtime_keys_performance_freeze_path():
    src = Path(prod.__file__).read_text(encoding="utf-8")
    assert "CANONICAL_PERFORMANCE_FREEZE_PATH" in src
    assert FREEZE_REL in src
    live_arm = _load_arm()
    assert prod._arm_payload_authorizes_at_commit(REPO, "120ac456df3a22884c48eed45852bdd001706f54", live_arm) is True
    live = _git("rev-parse", "HEAD")
    if live != "120ac456df3a22884c48eed45852bdd001706f54":
        assert prod._arm_payload_authorizes_at_commit(REPO, live, live_arm) is False
        assert prod.production_monte_carlo_arm_authorized() is False


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda p: p.__setitem__("freeze_parent_head", "0" * 40), "wrong freeze parent"),
        (
            lambda p: p.__setitem__("authorized_execution_commit", "1" * 40),
            "wrong freeze parent",
        ),
        (
            lambda p: p.__setitem__("reviewed_implementation_head", "2" * 40),
            "wrong reviewed implementation HEAD",
        ),
        (
            lambda p: p.__setitem__("reviewed_implementation_tree", "3" * 40),
            "wrong reviewed implementation TREE",
        ),
        (
            lambda p: p.__setitem__("freeze_artifact_sha256", "a" * 64),
            "wrong freeze artifact SHA",
        ),
        (lambda p: p.__setitem__("freeze_artifact_size", 1), "wrong freeze artifact size"),
        (
            lambda p: p["execution_authority_sha256"].__setitem__("lib", "b" * 64),
            "wrong lib hash",
        ),
        (
            lambda p: p["execution_authority_sha256"].__setitem__("runner", "c" * 64),
            "wrong runner hash",
        ),
        (
            lambda p: p["execution_authority_sha256"].__setitem__("auth", "d" * 64),
            "wrong auth hash",
        ),
        (
            lambda p: p["execution_authority_sha256"].__setitem__("production", "e" * 64),
            "wrong production hash",
        ),
        (
            lambda p: p["execution_authority_sha256"].__setitem__("worker", "f" * 64),
            "wrong worker hash",
        ),
        (lambda p: p["execution_tcb"][4].__setitem__("size", 1), "wrong worker hash/size"),
        (lambda p: p.__setitem__("prereg_json_sha256", "1" * 64), "wrong prereg hashes"),
        (
            lambda p: p.__setitem__("authorized_plan_sha256", "2" * 64),
            "wrong frozen plan identity",
        ),
        (
            lambda p: p.__setitem__("authorization_consumed", True),
            "protected state already consumed",
        ),
        (lambda p: p.__setitem__("production_result_minted", True), "RESULT already present"),
        (
            lambda p: p.__setitem__("world_records_persisted", True),
            "WORLD_RECORDS already present",
        ),
        (lambda p: p.__setitem__("production_executed", True), "production already executed"),
        (
            lambda p: p["superseded_unused_arm_0abc5fe"].__setitem__("head", "0" * 40),
            "superseded/old ARM",
        ),
    ],
    ids=[
        "wrong_freeze_parent",
        "non_matching_authorized_commit",
        "wrong_reviewed_head",
        "wrong_reviewed_tree",
        "wrong_freeze_sha",
        "wrong_freeze_size",
        "wrong_lib",
        "wrong_runner",
        "wrong_auth",
        "wrong_production",
        "wrong_worker",
        "wrong_worker_size",
        "wrong_prereg",
        "wrong_plan",
        "consumed",
        "result_present",
        "world_records_present",
        "already_executed",
        "old_arm",
    ],
)
def test_tampered_arm_contract_refused(mutator, match):
    payload = copy.deepcopy(_load_arm())
    mutator(payload)
    with pytest.raises(ArmContractError, match=match):
        validate_performance_production_arm(payload)


def test_arm_contract_tests_do_not_start_production():
    src = Path(__file__).read_text(encoding="utf-8")
    forbidden = (
        "run_canonical" + "_production_execution",
        "spawn_canonical" + "_production_process",
        "--run-production" + "-grid",
    )
    for token in forbidden:
        assert src.count(token) == 0
