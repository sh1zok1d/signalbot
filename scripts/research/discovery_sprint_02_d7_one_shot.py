"""Dormant D7 one-shot scientific execution runner.

Outcome-blind freeze unit. Import does not execute science.
``execute_one_shot()`` is the only canonical route and must not be invoked
on real CORE in this freeze unit.

Ordering is load-bearing:

1. refuse existing RESULT
2. verify tracked permit / authority hashes
3. load legal CORE 2020-2024 through the reviewed exact-byte loader
4. reconstruct hours and D7 states
5. recompute selector identity without reading t+1 target booleans
6. only then construct the scientific target vector
7. call the reviewed ``evaluate_d7_scientific`` exactly once
8. persist the evaluator classification without reinterpretation
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.research import discovery_sprint_02_impl as I


UNIT = "DISCOVERY_SPRINT_02_SCIENTIFIC_EXECUTION_FREEZE"
ONE_SHOT_UNIT = "DISCOVERY_SPRINT_02_D7_ONE_SHOT_SCIENTIFIC_EXECUTION"
D7_NAME = "KLINE_FLOW_IMPACT_STATE"
KIND = "CANONICAL_ONE_SHOT_SCIENTIFIC_EXECUTION"
BASE_MAIN_SHA = "55e3663b0951088261ee7b67bc70a4611bd8ba58"
# Exact main commit/tree this freeze unit branched from. Not the current PR tip.
# A tracked freeze artifact cannot truthfully store CURRENT_PR_HEAD: writing
# that SHA into the artifact would itself create another commit.
AUTHORITY_PARENT_COMMIT = BASE_MAIN_SHA
AUTHORITY_PARENT_TREE = "fb8516d07eb534626c9b53104eea6208f40ebb9b"
PROVENANCE_MODEL = "AUTHORITY_PARENT_PLUS_FILE_HASHES"

_PERMIT_WRITE_FORBIDDEN = False

PERMIT_REL = "docs/research/DISCOVERY_SPRINT_02_D7_EXECUTION_PERMIT.json"
RESULT_JSON_REL = "docs/research/DISCOVERY_SPRINT_02_D7_RESULT.json"
RESULT_MD_REL = "docs/research/DISCOVERY_SPRINT_02_D7_RESULT.md"
FREEZE_JSON_REL = "docs/research/DISCOVERY_SPRINT_02_SCIENTIFIC_EXECUTION_FREEZE.json"
FREEZE_MD_REL = "docs/research/DISCOVERY_SPRINT_02_SCIENTIFIC_EXECUTION_FREEZE.md"
REVIEW_JSON_REL = "docs/research/DISCOVERY_SPRINT_02_IMPLEMENTATION_REVIEW.json"
FEASIBILITY_JSON_REL = "docs/research/DISCOVERY_SPRINT_02_FEASIBILITY.json"
IMPL_REL = "scripts/research/discovery_sprint_02_impl.py"
FEAS_CLI_REL = "scripts/research/discovery_sprint_02_feasibility.py"
RUNNER_REL = "scripts/research/discovery_sprint_02_d7_one_shot.py"
EXECUTION_HEAD_RELS = (RUNNER_REL, IMPL_REL, PERMIT_REL, FREEZE_JSON_REL)
ANALYSIS_N = I.D7_TARGET_ELIGIBLE_ROWS
CANDIDATE_N = I.D7_SELECTOR_N

FROZEN_DISCOVERY_SPRINT_02_SHA256 = (
    "b95305e67d5b7ca6e81303ee43b0f38d2605d5de240ed3840d8ffafb2d27c49b"
)
FROZEN_FEASIBILITY_JSON_SHA256 = (
    "08ac5f9de90d9748b2cd5fe702c806760cdbcf613566718753626277beb35e6b"
)
FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256 = (
    "0fc3cb98875537149c3d1a5102cd2417736bd13f4db18050e8424095cb5f04f4"
)
FROZEN_REVIEWED_IMPLEMENTATION_SHA256 = (
    "965c6ccd58283e0a311b1bba03c981ce4a2aeb6f2bca308f4d75ada6843c5b65"
)
FROZEN_FEASIBILITY_CLI_SHA256 = (
    "54467f6ffa34fb1b6907332385f8ee0bf7084f384cd3b0f1648b2c09ec9b59f2"
)
FROZEN_FEASIBILITY_ARTIFACT_SHA256 = (
    "a737ef91c249306634148f4db8e757c985814c06b82a3c3627e07562784323c2"
)
FROZEN_FEASIBILITY_RUN_IDENTITY = (
    "a8955638479fe454d07e1cd6b52e2914d58d8da66133e787683b0274c1a2e6f9"
)

COMPARATOR = "RATE_MATCHED_RANDOM_STATE"
PRIMARY_TARGET = "NEXT_HOUR_HIGH_IMPACT_STATE"


class OneShotExecutionError(RuntimeError):
    """Fail-closed one-shot lifecycle error. Not a scientific classification."""


class TargetBeforeIdentityError(OneShotExecutionError):
    """Scientific target construction ran before the identity gate."""


@dataclass
class D7OneShotSession:
    authorities_ok: bool = False
    identity_ok: bool = False
    target_constructed: bool = False
    evaluator_called: bool = False
    permit_commit: str | None = None
    opened_files: list[str] = field(default_factory=list)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _assert_git_worktree(repo: Path) -> None:
    """Require `repo` itself to be a git worktree. No fallback."""

    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        raise OneShotExecutionError("REPO_NOT_GIT_WORKTREE")
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode != 0:
        raise OneShotExecutionError("REPO_NOT_GIT_WORKTREE")
    if Path(top.stdout.strip()).resolve() != Path(repo).resolve():
        raise OneShotExecutionError("GIT_TOPLEVEL_NE_REPO")


def _git(repo: Path, *args: str) -> str:
    _assert_git_worktree(repo)
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise OneShotExecutionError(f"GIT_COMMAND_FAILED:{args[0]}")
    return proc.stdout.strip()


def _git_bytes(repo: Path, *args: str) -> bytes:
    _assert_git_worktree(repo)
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise OneShotExecutionError(f"GIT_COMMAND_FAILED:{args[0]}")
    return proc.stdout


def verify_execution_checkout(repo: Path) -> str:
    """Fail closed unless repo is a clean git worktree matching HEAD blobs."""

    _assert_git_worktree(repo)
    head = _git(repo, "rev-parse", "HEAD")
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *EXECUTION_HEAD_RELS],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if dirty.returncode != 0:
        raise OneShotExecutionError("EXECUTION_TREE_DIRTY")
    for rel in EXECUTION_HEAD_RELS:
        path = repo / rel
        if not path.is_file():
            raise OneShotExecutionError(f"MISSING_HEAD_AUTHORITY:{rel}")
        blob = _git_bytes(repo, "show", f"HEAD:{rel}")
        if path.read_bytes() != blob:
            raise OneShotExecutionError(f"HEAD_BLOB_NE_DISK:{rel}")
    return head


def result_exists(repo: Path) -> bool:
    return (repo / RESULT_JSON_REL).is_file() or (repo / RESULT_MD_REL).is_file()


def refuse_if_result_exists(repo: Path) -> None:
    if result_exists(repo):
        raise OneShotExecutionError("RESULT_ALREADY_EXISTS_RERUN_FORBIDDEN")


def current_runner_sha256(repo: Path) -> str:
    """SHA256 of the on-disk one-shot runner. Not a self-digest constant."""

    path = repo / RUNNER_REL
    if not path.is_file():
        raise OneShotExecutionError("MISSING_ONE_SHOT_RUNNER")
    return I.file_sha256(path)


def current_authority_hashes(repo: Path) -> dict[str, str]:
    payload = json.loads((repo / FEASIBILITY_JSON_REL).read_text(encoding="utf-8"))
    return {
        "DISCOVERY_SPRINT_02_SHA256": I.file_sha256(repo / I.SPRINT_JSON_REL),
        "FEASIBILITY_JSON_SHA256": I.file_sha256(repo / FEASIBILITY_JSON_REL),
        "IMPLEMENTATION_REVIEW_JSON_SHA256": I.file_sha256(repo / REVIEW_JSON_REL),
        "REVIEWED_IMPLEMENTATION_SHA256": I.file_sha256(repo / IMPL_REL),
        "FEASIBILITY_CLI_SHA256": I.file_sha256(repo / FEAS_CLI_REL),
        "FEASIBILITY_ARTIFACT_SHA256": I.feasibility_artifact_sha256(payload),
        "FEASIBILITY_RUN_IDENTITY": str(payload.get("RUN_IDENTITY") or ""),
        "ONE_SHOT_RUNNER_SHA256": current_runner_sha256(repo),
    }


def permit_binding_payload(repo: Path) -> dict[str, Any]:
    hashes = current_authority_hashes(repo)
    return {
        "UNIT": UNIT,
        "D7_NAME": D7_NAME,
        "ONE_SHOT_UNIT": ONE_SHOT_UNIT,
        "EXECUTION_AUTHORIZED": True,
        "ONE_SHOT": True,
        "RERUN_AUTHORIZED": False,
        "BASE_MAIN_SHA": BASE_MAIN_SHA,
        "CORE_BTC_SNAPSHOT_ID": I.CORE_BTC_SNAPSHOT_ID,
        "DATA_IDENTITY_MODE": I.DATA_IDENTITY_MODE,
        "DISCOVERY_SPRINT_02_SHA256": hashes["DISCOVERY_SPRINT_02_SHA256"],
        "FEASIBILITY_JSON_SHA256": hashes["FEASIBILITY_JSON_SHA256"],
        "IMPLEMENTATION_REVIEW_JSON_SHA256": hashes["IMPLEMENTATION_REVIEW_JSON_SHA256"],
        "REVIEWED_IMPLEMENTATION_SHA256": hashes["REVIEWED_IMPLEMENTATION_SHA256"],
        "FEASIBILITY_CLI_SHA256": hashes["FEASIBILITY_CLI_SHA256"],
        "FEASIBILITY_ARTIFACT_SHA256": hashes["FEASIBILITY_ARTIFACT_SHA256"],
        "FEASIBILITY_RUN_IDENTITY": hashes["FEASIBILITY_RUN_IDENTITY"],
        "ONE_SHOT_RUNNER_SHA256": hashes["ONE_SHOT_RUNNER_SHA256"],
        "D7_SELECTOR_N": I.D7_SELECTOR_N,
        "D7_SELECTOR_DIGEST": I.D7_SELECTOR_DIGEST,
        "D7_CONSTRUCTED_HOURS": I.D7_CONSTRUCTED_HOURS,
        "D7_VALID_IMPACT_ROWS": I.D7_VALID_IMPACT_ROWS,
        "D7_TARGET_ELIGIBLE_ROWS": I.D7_TARGET_ELIGIBLE_ROWS,
        "D7_SEED": I.D7_SEED,
        "N_RANDOM_CONTROLS": I.N_RANDOM_CONTROLS,
        "D7_PRACTICAL_GATE": I.D7_PRACTICAL_GATE,
        "D7_TEMPORAL_YEARS_REQUIRED": I.D7_TEMPORAL_YEARS_REQUIRED,
        "PERCENTILE_METHOD": I.PERCENTILE_METHOD,
        "COMPARATOR": COMPARATOR,
        "PRIMARY_TARGET": PRIMARY_TARGET,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "D8_STATUS": I.D8_STATUS,
        "D8_SCIENTIFIC_EXECUTION_ELIGIBLE": False,
        "MARKET_07_CREATED": False,
    }


def compute_run_identity(bindings: Mapping[str, Any]) -> str:
    body = {key: value for key, value in bindings.items() if key != "RUN_IDENTITY"}
    return I.run_identity_payload(body)


def expected_permit(repo: Path) -> dict[str, Any]:
    payload = permit_binding_payload(repo)
    payload["RUN_IDENTITY"] = compute_run_identity(payload)
    return payload


def write_permit(repo: Path) -> dict[str, Any]:
    """Freeze-lifecycle only. ``execute_one_shot`` must never call this."""

    if _PERMIT_WRITE_FORBIDDEN:
        raise OneShotExecutionError("EXECUTE_ONE_SHOT_MUST_NOT_WRITE_PERMIT")
    payload = expected_permit(repo)
    (repo / PERMIT_REL).write_text(I.canonical_json(payload), encoding="utf-8")
    return payload


def verify_tracked_permit(repo: Path) -> dict[str, Any]:
    path = repo / PERMIT_REL
    if not path.is_file():
        raise OneShotExecutionError("MISSING_EXECUTION_PERMIT")
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise OneShotExecutionError("PERMIT_BYTES_UNPARSEABLE") from exc
    if not isinstance(stored, dict):
        raise OneShotExecutionError("PERMIT_NOT_OBJECT")
    runner_sha = current_runner_sha256(repo)
    if stored.get("ONE_SHOT_RUNNER_SHA256") != runner_sha:
        raise OneShotExecutionError("RUNNER_SHA256_NE_PERMIT")
    expected = expected_permit(repo)
    raw = path.read_text(encoding="utf-8")
    if raw != I.canonical_json(expected) or stored != expected:
        raise OneShotExecutionError("PERMIT_BYTES_NE_EXPECTED_AUTHORITY")
    if stored.get("ONE_SHOT") is not True:
        raise OneShotExecutionError("PERMIT_ONE_SHOT_NOT_TRUE")
    if stored.get("RERUN_AUTHORIZED") is not False:
        raise OneShotExecutionError("PERMIT_RERUN_AUTHORIZED_NOT_FALSE")
    if stored.get("EXECUTION_AUTHORIZED") is not True:
        raise OneShotExecutionError("PERMIT_EXECUTION_NOT_AUTHORIZED")
    if stored.get("D8_SCIENTIFIC_EXECUTION_ELIGIBLE") is not False:
        raise OneShotExecutionError("PERMIT_D8_MUST_REMAIN_NON_EXECUTABLE")
    hashes = current_authority_hashes(repo)
    frozen = {
        "DISCOVERY_SPRINT_02_SHA256": FROZEN_DISCOVERY_SPRINT_02_SHA256,
        "FEASIBILITY_JSON_SHA256": FROZEN_FEASIBILITY_JSON_SHA256,
        "IMPLEMENTATION_REVIEW_JSON_SHA256": FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256,
        "REVIEWED_IMPLEMENTATION_SHA256": FROZEN_REVIEWED_IMPLEMENTATION_SHA256,
        "FEASIBILITY_CLI_SHA256": FROZEN_FEASIBILITY_CLI_SHA256,
        "FEASIBILITY_ARTIFACT_SHA256": FROZEN_FEASIBILITY_ARTIFACT_SHA256,
        "FEASIBILITY_RUN_IDENTITY": FROZEN_FEASIBILITY_RUN_IDENTITY,
    }
    for key, expected_hash in frozen.items():
        if hashes[key] != expected_hash:
            raise OneShotExecutionError(f"AUTHORITY_HASH_MISMATCH:{key}")
        if stored.get(key) != expected_hash:
            raise OneShotExecutionError(f"PERMIT_HASH_MISMATCH:{key}")
    return stored


def verify_tracked_freeze(
    repo: Path, *, permit: Mapping[str, Any]
) -> dict[str, Any]:
    path = repo / FREEZE_JSON_REL
    if not path.is_file():
        raise OneShotExecutionError("MISSING_EXECUTION_FREEZE")
    try:
        freeze = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise OneShotExecutionError("FREEZE_BYTES_UNPARSEABLE") from exc
    if not isinstance(freeze, dict):
        raise OneShotExecutionError("FREEZE_NOT_OBJECT")
    if freeze.get("STATUS") != "FROZEN":
        raise OneShotExecutionError("FREEZE_STATUS_NE_FROZEN")
    if freeze.get("SCOPE") != "D7_ONLY":
        raise OneShotExecutionError("FREEZE_SCOPE_NE_D7_ONLY")
    runner = current_runner_sha256(repo)
    impl = I.file_sha256(repo / IMPL_REL)
    permit_sha = I.file_sha256(repo / PERMIT_REL)
    if freeze.get("ONE_SHOT_RUNNER_SHA256") != permit.get("ONE_SHOT_RUNNER_SHA256"):
        raise OneShotExecutionError("FREEZE_RUNNER_SHA_NE_PERMIT")
    if freeze.get("ONE_SHOT_RUNNER_SHA256") != runner:
        raise OneShotExecutionError("FREEZE_RUNNER_SHA_NE_DISK")
    if freeze.get("RUN_IDENTITY") != permit.get("RUN_IDENTITY"):
        raise OneShotExecutionError("FREEZE_RUN_IDENTITY_NE_PERMIT")
    if freeze.get("EXECUTION_PERMIT_SHA256") != permit_sha:
        raise OneShotExecutionError("FREEZE_PERMIT_SHA_MISMATCH")
    if freeze.get("REVIEWED_IMPLEMENTATION_SHA256") != permit.get(
        "REVIEWED_IMPLEMENTATION_SHA256"
    ):
        raise OneShotExecutionError("FREEZE_IMPL_SHA_NE_PERMIT")
    if freeze.get("REVIEWED_IMPLEMENTATION_SHA256") != impl:
        raise OneShotExecutionError("FREEZE_IMPL_SHA_NE_DISK")
    if freeze.get("D7_EXECUTION_AUTHORIZED") is not True:
        raise OneShotExecutionError("FREEZE_D7_EXECUTION_NOT_AUTHORIZED")
    if freeze.get("D7_EXECUTED") is not False:
        raise OneShotExecutionError("FREEZE_D7_ALREADY_EXECUTED")
    if freeze.get("D8_EXECUTION_AUTHORIZED") is not False:
        raise OneShotExecutionError("FREEZE_D8_EXECUTION_AUTHORIZED")
    if freeze.get("D8_EXECUTED") is not False:
        raise OneShotExecutionError("FREEZE_D8_EXECUTED")
    if freeze.get("SCIENTIFIC_OUTCOMES_COMPUTED") is not False:
        raise OneShotExecutionError("FREEZE_SCIENTIFIC_OUTCOMES_COMPUTED")
    if freeze.get("PROTECTED_2025_OPENED") is not False:
        raise OneShotExecutionError("FREEZE_PROTECTED_2025_OPENED")
    if freeze.get("PROTECTED_2026_OPENED") is not False:
        raise OneShotExecutionError("FREEZE_PROTECTED_2026_OPENED")
    if freeze.get("MARKET_07_CREATED") is not False:
        raise OneShotExecutionError("FREEZE_MARKET_07_CREATED")
    return freeze


def frozen_d7_strata(repo: Path) -> dict[str, dict[str, int]]:
    payload = json.loads((repo / FEASIBILITY_JSON_REL).read_text(encoding="utf-8"))
    d7 = payload.get("D7")
    if not isinstance(d7, dict):
        raise OneShotExecutionError("FEASIBILITY_D7_OBJECT_MISSING")
    eligible = d7.get("TARGET_ELIGIBLE_BY_YEAR_RV_BUCKET")
    candidate = d7.get("CANDIDATE_BY_YEAR_RV_BUCKET")
    if not isinstance(eligible, dict) or not isinstance(candidate, dict):
        raise OneShotExecutionError("FEASIBILITY_D7_STRATA_MISSING")
    return {
        "TARGET_ELIGIBLE_BY_YEAR_RV_BUCKET": {
            str(key): int(value) for key, value in eligible.items()
        },
        "CANDIDATE_BY_YEAR_RV_BUCKET": {
            str(key): int(value) for key, value in candidate.items()
        },
    }


def assert_frozen_d7_strata(census: Mapping[str, Any], repo: Path) -> None:
    frozen = frozen_d7_strata(repo)
    got_eligible = {
        str(key): int(value)
        for key, value in dict(census.get("TARGET_ELIGIBLE_BY_YEAR_RV_BUCKET") or {}).items()
    }
    got_candidate = {
        str(key): int(value)
        for key, value in dict(census.get("CANDIDATE_BY_YEAR_RV_BUCKET") or {}).items()
    }
    if got_eligible != frozen["TARGET_ELIGIBLE_BY_YEAR_RV_BUCKET"]:
        raise OneShotExecutionError("TARGET_ELIGIBLE_STRATA_MISMATCH")
    if got_candidate != frozen["CANDIDATE_BY_YEAR_RV_BUCKET"]:
        raise OneShotExecutionError("CANDIDATE_STRATA_MISMATCH")
    if sum(got_eligible.values()) != I.D7_TARGET_ELIGIBLE_ROWS:
        raise OneShotExecutionError("TARGET_ELIGIBLE_STRATA_SUM_MISMATCH")
    if sum(got_candidate.values()) != I.D7_SELECTOR_N:
        raise OneShotExecutionError("CANDIDATE_STRATA_SUM_MISMATCH")


def assert_scientific_array_identity(arrays: Mapping[str, Any]) -> None:
    """Structural population identity. Does not inspect target success rates."""

    n = ANALYSIS_N
    k = CANDIDATE_N
    for field in ("target", "candidate", "year", "rv_bucket", "target_eligible"):
        if len(arrays[field]) != n:
            raise OneShotExecutionError(f"ANALYSIS_N_MISMATCH:{field}:{len(arrays[field])}")
    if int(sum(bool(row) for row in arrays["candidate"])) != k:
        raise OneShotExecutionError("CANDIDATE_N_MISMATCH")
    if not all(bool(row) is True for row in arrays["target_eligible"]):
        raise OneShotExecutionError("TARGET_ELIGIBLE_NOT_ALL_TRUE")


def verify_pre_scientific_authorities(
    repo: Path, *, session: D7OneShotSession | None = None
) -> dict[str, Any]:
    permit = verify_tracked_permit(repo)
    if permit.get("CORE_BTC_SNAPSHOT_ID") != I.CORE_BTC_SNAPSHOT_ID:
        raise OneShotExecutionError("PERMIT_CORE_BTC_SNAPSHOT_MISMATCH")
    if permit.get("DATA_IDENTITY_MODE") != I.DATA_IDENTITY_MODE:
        raise OneShotExecutionError("PERMIT_DATA_IDENTITY_MODE_MISMATCH")
    if permit.get("RUN_IDENTITY") != compute_run_identity(permit):
        raise OneShotExecutionError("PERMIT_RUN_IDENTITY_MISMATCH")
    freeze = verify_tracked_freeze(repo, permit=permit)
    authority = I.verify_dataset_authority(repo)
    if authority["DATA_IDENTITY_MODE"] != I.DATA_IDENTITY_MODE:
        raise OneShotExecutionError("DATA_IDENTITY_MODE_MISMATCH")
    if authority["CORE_BTC_SNAPSHOT_ID"] != I.CORE_BTC_SNAPSHOT_ID:
        raise OneShotExecutionError("CORE_BTC_SNAPSHOT_MISMATCH")
    if authority["MANIFEST_RESEARCH_AUTHORIZED"] is not True:
        raise OneShotExecutionError("MANIFEST_RESEARCH_NOT_AUTHORIZED")
    if authority["MANIFEST_CONFIRMATORY_AUTHORIZED"] is not False:
        raise OneShotExecutionError("MANIFEST_CONFIRMATORY_MUST_REMAIN_FALSE")
    if session is not None:
        session.authorities_ok = True
    return {"permit": permit, "freeze": freeze, "authority": authority}


def reconstruct_d7_selector_identity(
    states: Sequence[I.D7HourState],
    *,
    repo: Path,
    session: D7OneShotSession | None = None,
) -> dict[str, Any]:
    """Recompute selector identity. Does not read t+1 target booleans."""

    census = I.d7_feasibility_census(states)
    if census.get("SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED") is not False:
        raise I.RealScientificOutcomeForbidden("IDENTITY_COMPUTED_TPLUS1")
    I.assert_d7_selector_identity(census)
    assert_frozen_d7_strata(census, repo)
    if session is not None:
        session.identity_ok = True
    return census


def construct_d7_scientific_arrays(
    states: Sequence[I.D7HourState],
    *,
    session: D7OneShotSession | None = None,
) -> dict[str, Any]:
    """Build t+1 target vectors. Forbidden before the identity gate."""

    if session is None or session.identity_ok is not True:
        raise TargetBeforeIdentityError("TARGET_BEFORE_IDENTITY_GATE")
    by_start = I.d7_index_by_hour_start(states)
    candidate: list[bool] = []
    target: list[bool] = []
    year: list[int] = []
    rv_bucket: list[int] = []
    target_eligible: list[bool] = []
    for row in states:
        next_start = row.hour.hour_start_ms + I.HOUR_MS
        next_idx = by_start.get(next_start)
        next_ok = (
            next_idx is not None
            and next_start < I.PROTECTED_START_MS
            and states[next_idx].d7_state is not None
            and row.rv_bucket is not None
        )
        if not next_ok:
            continue
        nxt = states[next_idx]
        candidate.append(row.d7_state is True)
        target.append(bool(nxt.d7_state))
        year.append(int(row.hour.year))
        rv_bucket.append(int(row.rv_bucket))
        target_eligible.append(True)
    if session is not None:
        session.target_constructed = True
    return {
        "candidate": candidate,
        "target": target,
        "year": year,
        "rv_bucket": rv_bucket,
        "target_eligible": target_eligible,
    }


def call_reviewed_d7_evaluator(
    arrays: Mapping[str, Any],
    *,
    session: D7OneShotSession | None = None,
) -> dict[str, Any]:
    if session is None or session.identity_ok is not True:
        raise OneShotExecutionError("EVALUATOR_BEFORE_IDENTITY_GATE")
    if session.target_constructed is not True:
        raise OneShotExecutionError("EVALUATOR_BEFORE_TARGET_CONSTRUCTION")
    if session.evaluator_called:
        raise OneShotExecutionError("EVALUATOR_ALREADY_CALLED")
    session.evaluator_called = True
    return I.evaluate_d7_scientific(
        candidate=arrays["candidate"],
        target=arrays["target"],
        year=arrays["year"],
        rv_bucket=arrays["rv_bucket"],
        target_eligible=arrays["target_eligible"],
    )


def wrap_one_shot_result(
    raw: Mapping[str, Any],
    *,
    permit: Mapping[str, Any],
    permit_commit: str,
    execution_permit_sha256: str,
) -> dict[str, Any]:
    if "CLASSIFICATION" not in raw:
        raise OneShotExecutionError("EVALUATOR_CLASSIFICATION_MISSING")
    classification = raw["CLASSIFICATION"]
    if classification not in ("D7_PROMISING_PROTOTYPE", "D7_NO_USEFUL_STRUCTURE"):
        raise OneShotExecutionError(f"UNEXPECTED_CLASSIFICATION:{classification}")
    return {
        "UNIT": ONE_SHOT_UNIT,
        "KIND": KIND,
        "D7_NAME": D7_NAME,
        "CLASSIFICATION": classification,
        "MU_D7_RULE": raw.get("MU_D7_RULE"),
        "MU_D7_CONTROL": raw.get("MU_D7_CONTROL"),
        "DELTA_D7": raw.get("DELTA_D7"),
        "CONTROL_D7_P95": raw.get("CONTROL_D7_P95"),
        "MC_P_D7": raw.get("MC_P_D7"),
        "YEARLY_DELTA_D7": raw.get("YEARLY_DELTA_D7"),
        "STATISTICAL_GATE": raw.get("STATISTICAL_GATE"),
        "PRACTICAL_GATE": raw.get("PRACTICAL_GATE"),
        "TEMPORAL_GATE": raw.get("TEMPORAL_GATE"),
        "ONE_SHOT": True,
        "EXECUTION_AUTHORIZED": True,
        "RERUN_AUTHORIZED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": True,
        "RUN_IDENTITY": permit["RUN_IDENTITY"],
        "PERMIT_COMMIT": permit_commit,
        "EXECUTION_PERMIT_SHA256": execution_permit_sha256,
        "D7_SELECTOR_N": I.D7_SELECTOR_N,
        "D7_SELECTOR_DIGEST": I.D7_SELECTOR_DIGEST,
        "ANALYSIS_N": ANALYSIS_N,
        "CANDIDATE_N": CANDIDATE_N,
        "CORE_BTC_SNAPSHOT_ID": I.CORE_BTC_SNAPSHOT_ID,
        "DATA_IDENTITY_MODE": I.DATA_IDENTITY_MODE,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "D8_EXECUTED": False,
        "D8_STATUS": I.D8_STATUS,
        "MARKET_07_CREATED": False,
        "EVIDENCE_LABEL": "ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA",
        "NOT_INDEPENDENT_CONFIRMATION": True,
        "NOT_PROVEN_ALPHA": True,
        "NOT_VALIDATED_TRADING_EDGE": True,
        "NOT_ORDERBOOK_LIQUIDITY_CLAIM": True,
    }


def result_payload_sha256(payload: Mapping[str, Any]) -> str:
    """SHA256 of canonical JSON excluding RESULT_PAYLOAD_SHA256 itself."""

    hashed = {
        key: value for key, value in payload.items() if key != "RESULT_PAYLOAD_SHA256"
    }
    return I.sha256_bytes(I.canonical_json(hashed).encode("utf-8"))


def render_result_markdown(result: Mapping[str, Any]) -> str:
    """Human-readable derivative. Not a second scientific authority."""

    return "\n".join(
        [
            "# Discovery Sprint 02 D7 canonical one-shot RESULT",
            "",
            f"CLASSIFICATION = `{result.get('CLASSIFICATION')}`",
            f"RUN_IDENTITY = `{result.get('RUN_IDENTITY')}`",
            f"RESULT_PAYLOAD_SHA256 = `{result.get('RESULT_PAYLOAD_SHA256')}`",
            f"EXECUTION_PERMIT_SHA256 = `{result.get('EXECUTION_PERMIT_SHA256')}`",
            "ONE_SHOT = true",
            "RERUN_AUTHORIZED = false",
            "",
            "Canonical JSON RESULT is the scientific payload.",
            "Markdown is a human-readable derivative, not a second authority.",
            "Evaluator classification is preserved without reinterpretation.",
            "NOT_PROVEN_ALPHA. NOT_VALIDATED_TRADING_EDGE.",
            "",
        ]
    )


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    directory = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def persist_result(repo: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    hashed = {
        key: value for key, value in payload.items() if key != "RESULT_PAYLOAD_SHA256"
    }
    digest = result_payload_sha256(hashed)
    written = dict(hashed)
    written["RESULT_PAYLOAD_SHA256"] = digest
    json_bytes = I.canonical_json(written).encode("utf-8")
    md_bytes = render_result_markdown(written).encode("utf-8")
    _atomic_write(repo / RESULT_JSON_REL, json_bytes)
    _atomic_write(repo / RESULT_MD_REL, md_bytes)
    return written


def execute_one_shot(repo: Path | None = None) -> dict[str, Any]:
    """Canonical D7 one-shot. Do not call on real CORE in the freeze unit.

    Consumes the already-tracked permit and freeze. Never regenerates them.
    """

    global _PERMIT_WRITE_FORBIDDEN
    base = repo if repo is not None else repo_root()
    session = D7OneShotSession()
    previous = _PERMIT_WRITE_FORBIDDEN
    _PERMIT_WRITE_FORBIDDEN = True
    try:
        refuse_if_result_exists(base)
        session.permit_commit = verify_execution_checkout(base)
        verified = verify_pre_scientific_authorities(base, session=session)
        log = I.OpenedFileLog()
        bars = I.load_legal_1m_bars(repo=base, log=log)
        for rel in log.files:
            if I.path_is_protected_partition(Path(rel)):
                raise I.ProtectedYearRefused(f"PROTECTED_PATH_OPENED:{rel}")
            lowered = rel.lower()
            if "/2025-" in lowered or "/2026-" in lowered:
                raise I.ProtectedYearRefused(f"PROTECTED_PATH_OPENED:{rel}")
        session.opened_files = list(log.files)
        hours = I.aggregate_completed_hours(bars)
        del bars
        states = I.build_d7_states(hours)
        reconstruct_d7_selector_identity(states, repo=base, session=session)
        arrays = construct_d7_scientific_arrays(states, session=session)
        assert_scientific_array_identity(arrays)
        raw = call_reviewed_d7_evaluator(arrays, session=session)
        wrapped = wrap_one_shot_result(
            raw,
            permit=verified["permit"],
            permit_commit=session.permit_commit,
            execution_permit_sha256=I.file_sha256(base / PERMIT_REL),
        )
        return persist_result(base, wrapped)
    finally:
        _PERMIT_WRITE_FORBIDDEN = previous


def freeze_payload(
    repo: Path,
    *,
    permit: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "UNIT": UNIT,
        "KIND": "OUTCOME_BLIND_SCIENTIFIC_EXECUTION_FREEZE",
        "STATUS": "FROZEN",
        "SCOPE": "D7_ONLY",
        "PROVENANCE_MODEL": PROVENANCE_MODEL,
        "PROVENANCE_MODEL_NOTE": (
            "AUTHORITY_PARENT_COMMIT/TREE identify the exact main commit this "
            "freeze unit branched from (BASE_MAIN_SHA). They are not the "
            "current PR tip. Frozen machinery is identified by file SHA256 "
            "values. CURRENT_PR_HEAD/CURRENT_PR_TREE are never stored here "
            "because writing them would require another commit and go stale."
        ),
        "BASE_MAIN_SHA": BASE_MAIN_SHA,
        "AUTHORITY_PARENT_COMMIT": AUTHORITY_PARENT_COMMIT,
        "AUTHORITY_PARENT_TREE": AUTHORITY_PARENT_TREE,
        "CURRENT_PR_HEAD_BOUND": False,
        "DISCOVERY_SPRINT_02_SHA256": FROZEN_DISCOVERY_SPRINT_02_SHA256,
        "FEASIBILITY_JSON_SHA256": FROZEN_FEASIBILITY_JSON_SHA256,
        "IMPLEMENTATION_REVIEW_JSON_SHA256": FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256,
        "REVIEWED_IMPLEMENTATION_SHA256": FROZEN_REVIEWED_IMPLEMENTATION_SHA256,
        "FEASIBILITY_CLI_SHA256": FROZEN_FEASIBILITY_CLI_SHA256,
        "FEASIBILITY_ARTIFACT_SHA256": FROZEN_FEASIBILITY_ARTIFACT_SHA256,
        "FEASIBILITY_RUN_IDENTITY": FROZEN_FEASIBILITY_RUN_IDENTITY,
        "EXECUTION_PERMIT_SHA256": I.file_sha256(repo / PERMIT_REL),
        "ONE_SHOT_RUNNER_SHA256": I.file_sha256(repo / RUNNER_REL),
        "RUN_IDENTITY": permit["RUN_IDENTITY"],
        "CORE_BTC_SNAPSHOT_ID": I.CORE_BTC_SNAPSHOT_ID,
        "DATA_IDENTITY_MODE": I.DATA_IDENTITY_MODE,
        "D7_NAME": D7_NAME,
        "D7_SELECTOR_N": I.D7_SELECTOR_N,
        "D7_SELECTOR_DIGEST": I.D7_SELECTOR_DIGEST,
        "D7_CONSTRUCTED_HOURS": I.D7_CONSTRUCTED_HOURS,
        "D7_VALID_IMPACT_ROWS": I.D7_VALID_IMPACT_ROWS,
        "D7_TARGET_ELIGIBLE_ROWS": I.D7_TARGET_ELIGIBLE_ROWS,
        "D7_SEED": I.D7_SEED,
        "N_RANDOM_CONTROLS": I.N_RANDOM_CONTROLS,
        "D7_PRACTICAL_GATE": I.D7_PRACTICAL_GATE,
        "D7_TEMPORAL_YEARS_REQUIRED": I.D7_TEMPORAL_YEARS_REQUIRED,
        "PERCENTILE_METHOD": I.PERCENTILE_METHOD,
        "COMPARATOR": COMPARATOR,
        "PRIMARY_TARGET": PRIMARY_TARGET,
        "STATISTICAL_GATE": "MU_D7_RULE > CONTROL_D7_P95",
        "PRACTICAL_GATE": "DELTA_D7 >= 0.05",
        "TEMPORAL_GATE": "YEARLY_DELTA_D7 > 0 in at least 3 of 5 years",
        "CLASSIFICATION_RULE": (
            "D7_PROMISING_PROTOTYPE iff STATISTICAL_GATE and PRACTICAL_GATE "
            "and TEMPORAL_GATE; otherwise D7_NO_USEFUL_STRUCTURE"
        ),
        "D7_EXECUTION_AUTHORIZED": True,
        "D7_EXECUTED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        "D8_STATUS": I.D8_STATUS,
        "D8_EXECUTION_AUTHORIZED": False,
        "D8_EXECUTED": False,
        "D8_SCIENTIFIC_EXECUTION_ELIGIBLE": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MARKET_07_CREATED": False,
        "NEXT_UNIT": ONE_SHOT_UNIT,
        "D7_RUNTIME_EXECUTABLE_DEPENDENCIES": [
            RUNNER_REL,
            IMPL_REL,
        ],
        "D7_RUNTIME_EXECUTABLE_DEPENDENCIES_NOTE": (
            "execute_one_shot imports discovery_sprint_02_impl only. impl "
            "scientific code uses numpy plus stdlib. feasibility CLI is a "
            "freeze-time authority hash, not imported at execution."
        ),
    }


def freeze_markdown(payload: Mapping[str, Any]) -> str:
    return f"""# Discovery Sprint 02 scientific execution freeze

**Unit:** `{payload["UNIT"]}`
**Status:** `{payload["STATUS"]}`
**Scope:** `{payload["SCOPE"]}`
**RUN_IDENTITY:** `{payload["RUN_IDENTITY"]}`

D7 one-shot route is frozen and authorized. D7 was not executed.
D8 remains non-executable. Scientific outcomes were not computed.

Provenance is non-self-referential: `AUTHORITY_PARENT_COMMIT` /
`AUTHORITY_PARENT_TREE` are the exact `main` commit this unit branched
from. They are not the current PR tip. Runner bytes are a pre-scientific
execution authority bound by the tracked permit.

```
BASE_MAIN_SHA = {payload["BASE_MAIN_SHA"]}
PROVENANCE_MODEL = {payload["PROVENANCE_MODEL"]}
AUTHORITY_PARENT_COMMIT = {payload["AUTHORITY_PARENT_COMMIT"]}
AUTHORITY_PARENT_TREE = {payload["AUTHORITY_PARENT_TREE"]}
CURRENT_PR_HEAD_BOUND = false
CORE_BTC_SNAPSHOT_ID = {payload["CORE_BTC_SNAPSHOT_ID"]}
DATA_IDENTITY_MODE = {payload["DATA_IDENTITY_MODE"]}
D7_SELECTOR_N = {payload["D7_SELECTOR_N"]}
D7_SELECTOR_DIGEST = {payload["D7_SELECTOR_DIGEST"]}
D7_SEED = {payload["D7_SEED"]}
N_RANDOM_CONTROLS = {payload["N_RANDOM_CONTROLS"]}
D7_EXECUTION_AUTHORIZED = true
D7_EXECUTED = false
D8_EXECUTION_AUTHORIZED = false
D8_EXECUTED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
NEXT_UNIT = {payload["NEXT_UNIT"]}
```
"""


def write_freeze_artifacts(repo: Path | None = None) -> dict[str, Any]:
    """Write permit + freeze artifacts. Does not execute D7 science."""

    if _PERMIT_WRITE_FORBIDDEN:
        raise OneShotExecutionError("EXECUTE_ONE_SHOT_MUST_NOT_WRITE_FREEZE")
    base = repo if repo is not None else repo_root()
    if result_exists(base):
        raise OneShotExecutionError("RESULT_EXISTS_FREEZE_REFUSED")
    permit = write_permit(base)
    verify_tracked_permit(base)
    I.verify_dataset_authority(base)
    payload = freeze_payload(base, permit=permit)
    (base / FREEZE_JSON_REL).write_text(I.canonical_json(payload), encoding="utf-8")
    (base / FREEZE_MD_REL).write_text(freeze_markdown(payload), encoding="utf-8")
    return {"PERMIT": permit, "FREEZE": payload}


def assert_runner_has_no_d8_route() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    # Tokens split so this helper's own source does not self-match.
    forbidden = (
        "evaluate_d8" + "_scientific(",
        "recovery_" + "6h(",
        "d8_feasibility_" + "census(",
        "execute_" + "d8",
    )
    for token in forbidden:
        if token in source:
            raise OneShotExecutionError(f"D8_ROUTE_PRESENT:{token}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sprint 02 D7 execution freeze (no scientific outcomes)"
    )
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--write-freeze", action="store_true")
    args = parser.parse_args(argv)
    if not args.write_freeze:
        raise SystemExit("D7_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED_IN_FREEZE_UNIT")
    assert_runner_has_no_d8_route()
    result = write_freeze_artifacts(repo=args.repo)
    print(
        I.canonical_json(
            {
                "STATUS": "FROZEN",
                "RUN_IDENTITY": result["PERMIT"]["RUN_IDENTITY"],
                "NEXT_UNIT": ONE_SHOT_UNIT,
                "SCIENTIFIC_OUTCOMES_COMPUTED": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
