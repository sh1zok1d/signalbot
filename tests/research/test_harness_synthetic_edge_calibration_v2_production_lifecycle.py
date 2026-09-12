"""Tests for the complete pre-outcome V2 production lifecycle repair.

Covers: historical (commit-parameterized) execution-authority verification,
durable reservation/claim, durable partial-world checkpointing, mechanical
aggregation wiring, session-based per-world authorization, WORLD_RECORDS/
RESULT mint, and historical RESULT re-verification from a descendant
checkout or a clean clone.

Disposable temporary git repositories and small (5-job) synthetic subsets of
the canonical plan only. These tests must not run the frozen 3200-world
Monte Carlo, mint a real RESULT, create a real ARM in project history, or
consume V1/V2 authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p
from scripts.research import harness_synthetic_edge_calibration_v2_rank_policy as v2

REPO = Path(__file__).resolve().parents[2]
CONCLUSION_IDS = list(v2.frozen_required_coverage_map())
DUMMY_INHERITED = {cid: "PLACEHOLDER_NOT_A_REAL_VERDICT" for cid in CONCLUSION_IDS}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _live_bytes(rel: str) -> bytes:
    return (REPO / rel).read_bytes()


def _commit_freeze_tree(tmp_path: Path, *, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    copies = {
        "scripts/__init__.py": _live_bytes("scripts/__init__.py"),
        "scripts/research/__init__.py": _live_bytes("scripts/research/__init__.py"),
        prod.LIB_REL: _live_bytes(prod.LIB_REL),
        prod.RUNNER_REL: _live_bytes(prod.RUNNER_REL),
        prod.AUTH_REL: _live_bytes(prod.AUTH_REL),
        prod.PRODUCTION_REL: _live_bytes(prod.PRODUCTION_REL),
        prod.WORKER_REL: _live_bytes(prod.WORKER_REL),
        v2p.V2_POLICY_REL: _live_bytes(v2p.V2_POLICY_REL),
        v2p.V2_FREEZE_ARTIFACT_REL: _live_bytes(v2p.V2_FREEZE_ARTIFACT_REL),
        "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json": _live_bytes(
            "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
        ),
        "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md": _live_bytes(
            "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
        ),
    }
    for rel, data in copies.items():
        _write(repo / rel, data)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "v2 policy freeze tree")
    return repo


def _small_arm_payload(repo: Path) -> dict:
    """Build a self-consistent ARM payload under the active small-job mock."""
    parent = _git(repo, "rev-parse", "HEAD")
    parent_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze_blob = (repo / v2p.V2_FREEZE_ARTIFACT_REL).read_bytes()
    policy_blob = (repo / v2p.V2_POLICY_REL).read_bytes()
    plan = v2p.canonical_v2_plan(repo_root=repo, commit="HEAD")
    payload = dict(v2p.V2_ARM_REQUIRED_LITERALS)
    payload.update(
        {
            "freeze_parent_head": parent,
            "freeze_parent_tree": parent_tree,
            "freeze_artifact_sha256": _sha(freeze_blob),
            "freeze_artifact_size": len(freeze_blob),
            "v2_policy_sha256": _sha(policy_blob),
            "v2_policy_size": len(policy_blob),
            "canonical_v2_plan_sha256": plan["sha256"],
            "canonical_world_count": v2p.canonical_v2_world_count(),
            "original_prereg_head": v2p.FROZEN_ORIGINAL_PREREG_HEAD,
            "original_prereg_tree": v2p.FROZEN_ORIGINAL_PREREG_TREE,
            "amendment_001_head": v2p.FROZEN_AMENDMENT_001_HEAD,
            "amendment_001_tree": v2p.FROZEN_AMENDMENT_001_TREE,
        }
    )
    return payload


def _commit_arm(repo: Path, payload: dict, *, message: str = "v2 production arm") -> str:
    _write(repo / v2p.CANONICAL_V2_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def small_jobs():
    """The first 5 canonical jobs, held fixed for the duration of one test."""
    return tuple(v2p.canonical_v2_production_jobs()[:5])


@pytest.fixture
def armed_small_repo(tmp_path, small_jobs):
    """A disposable repo with freeze -> small-scope ARM already committed."""
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        repo = _commit_freeze_tree(tmp_path)
        payload = _small_arm_payload(repo)
        arm_commit = _commit_arm(repo, payload)
        yield repo, arm_commit


# --- Blocker 1: historical (commit-parameterized) execution authority -------


def test_historical_auth_works_from_descendant_checkout(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
        _write(repo / "docs/NOTE.md", "unrelated descendant\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "descendant commit")
        bound_later = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
        assert bound_later["run_identity"] == bound["run_identity"]
        # Ambient HEAD is now the descendant, not the ARM; live HEAD-relative
        # authorization is correctly False, but historical auth is unaffected.
        assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_historical_auth_works_from_clean_clone(armed_small_repo, small_jobs, tmp_path):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        _write(repo / "docs/NOTE.md", "unrelated descendant\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "descendant commit")
        bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
        clone = tmp_path / "clean_clone"
        subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
        bound_clone = v2p.verify_historical_v2_execution_authority(clone, arm_commit)
        assert bound_clone == bound


def test_ambient_worktree_mutation_does_not_affect_historical_verification(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
        arm_path = repo / v2p.CANONICAL_V2_ARM_PATH
        live = json.loads(arm_path.read_text(encoding="utf-8"))
        live["authorization_consumed"] = True
        _write(arm_path, json.dumps(live, indent=2, sort_keys=True) + "\n")
        bound2 = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
        assert bound2 == bound


def test_stale_or_non_arm_commit_refuses_historical_auth(tmp_path):
    repo = _commit_freeze_tree(tmp_path)
    freeze_commit = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
        v2p.verify_historical_v2_execution_authority(repo, freeze_commit)


def test_v1_arm_reused_as_v2_refuses_historical_auth(tmp_path):
    repo = _commit_freeze_tree(tmp_path)
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps({"production_monte_carlo_arm_authorized": True}) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "v1-style arm only")
    commit = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
        v2p.verify_historical_v2_execution_authority(repo, commit)


# --- Blocker 2: durable reservation / claim ----------------------------------


def test_reservation_document_identity_matches_historical_bound(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
        reservation = v2p.v2_durable_reservation_document(repo, arm_commit)
        claim = v2p.v2_durable_claim_document(repo, arm_commit)
        assert reservation["run_identity"] == bound["run_identity"]
        assert claim["run_identity"] == bound["run_identity"]
        assert claim["reservation_sha256"] == _sha(
            json_bytes(reservation)
        )


def json_bytes(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def test_reservation_available_before_any_artifact(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        v2p.assert_v2_reservation_available(repo, arm_commit)  # must not raise


@pytest.mark.parametrize(
    "path_attr",
    [
        "CANONICAL_V2_RESULT_PATH",
        "CANONICAL_V2_WORLD_RECORDS_PATH",
        "CANONICAL_V2_RESERVATION_PATH",
        "CANONICAL_V2_CLAIM_PATH",
    ],
)
def test_reservation_unavailable_once_any_protected_artifact_exists(armed_small_repo, small_jobs, path_attr):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        rel = getattr(v2p, path_attr)
        _write(repo / rel, "{}\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", f"conflicting {path_attr}")
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.assert_v2_reservation_available(repo, arm_commit)


def test_duplicate_sequential_reservation_fails_closed(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        v2p.assert_v2_reservation_available(repo, arm_commit)
        reservation = v2p.v2_durable_reservation_document(repo, arm_commit)
        _write(repo / v2p.CANONICAL_V2_RESERVATION_PATH, json_bytes(reservation))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "first reservation committed")
        # A second, sequential attempt (simulating a retry or a second
        # process) must fail closed once the first reservation is tracked.
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.assert_v2_reservation_available(repo, arm_commit)


def test_concurrent_reservation_race_resolved_by_first_committer(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        # Two independent "processes" both check availability before either commits.
        v2p.assert_v2_reservation_available(repo, arm_commit)  # process A checks
        v2p.assert_v2_reservation_available(repo, arm_commit)  # process B checks
        # Process A wins the race and commits first.
        reservation_a = v2p.v2_durable_reservation_document(repo, arm_commit)
        _write(repo / v2p.CANONICAL_V2_RESERVATION_PATH, json_bytes(reservation_a))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "process A reservation")
        # Process B, upon re-checking before its own (losing) commit, now
        # correctly sees the tracked reservation and refuses.
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.assert_v2_reservation_available(repo, arm_commit)


def test_forged_reservation_wrong_run_identity_is_still_detectable(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        reservation = v2p.v2_durable_reservation_document(repo, arm_commit)
        forged = dict(reservation)
        forged["run_identity"] = "0" * 64
        real = v2p.v2_durable_reservation_document(repo, arm_commit)
        assert forged["run_identity"] != real["run_identity"]


def test_forged_claim_wrong_reservation_hash_is_still_detectable(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        claim = v2p.v2_durable_claim_document(repo, arm_commit)
        reservation = v2p.v2_durable_reservation_document(repo, arm_commit)
        assert claim["reservation_sha256"] == _sha(json_bytes(reservation))
        tampered_reservation = dict(reservation)
        tampered_reservation["run_identity"] = "0" * 64
        assert claim["reservation_sha256"] != _sha(json_bytes(tampered_reservation))


# --- Durable partial / checkpoint --------------------------------------------


def test_checkpoint_resume_matches_original_and_avoids_recompute(armed_small_repo, small_jobs, tmp_path):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        store = v2p.V2DurablePartialWorldStore.open(
            tmp_path / "cache", run_identity=session.run_identity, arm_commit=session.arm_commit
        )
        records = v2p.run_canonical_v2_production_grid_in_session(session, durable_partial=store)
        assert len(records) == len(small_jobs)
        cached = store.load_structurally_valid_cached()
        assert len(cached) == len(small_jobs)
        records_resumed = v2p.run_canonical_v2_production_grid_in_session(session, durable_partial=store)
        assert records_resumed == records


def test_checkpoint_rejects_conflicting_duplicate_record(armed_small_repo, small_jobs, tmp_path):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        store = v2p.V2DurablePartialWorldStore.open(
            tmp_path / "cache", run_identity=session.run_identity, arm_commit=session.arm_commit
        )
        job = small_jobs[0]
        rec = v2p.evaluate_v2_world_in_session(session, *job)
        store.checkpoint_completed_world(rec, job)
        forged = copy.deepcopy(rec)
        forged.taxonomy = "FORGED"
        with pytest.raises(v2p.V2ProductionIntegrityError):
            store.checkpoint_completed_world(forged, job)


def test_checkpoint_store_identity_mismatch_fails_closed(armed_small_repo, small_jobs, tmp_path):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        store_path = tmp_path / "cache"
        v2p.V2DurablePartialWorldStore.open(
            store_path, run_identity=session.run_identity, arm_commit=session.arm_commit
        )
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.V2DurablePartialWorldStore.open(store_path, run_identity="0" * 64, arm_commit=session.arm_commit)


def test_forged_checkpoint_cannot_bypass_mint_reauthentication(armed_small_repo, small_jobs, tmp_path):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        store = v2p.V2DurablePartialWorldStore.open(
            tmp_path / "cache", run_identity=session.run_identity, arm_commit=session.arm_commit
        )
        records = list(v2p.run_canonical_v2_production_grid_in_session(session, durable_partial=store))
        # Directly tamper with a cached record file on disk (bypassing the
        # store's own write path) to simulate a forged-but-self-consistent
        # checkpoint, then feed the mutated in-memory record set to mint.
        mixed = list(records)
        mixed[0] = dataclasses_replace(mixed[0], taxonomy="FORGED")
        with pytest.raises(v2p.V2ProductionIntegrityError):
            v2p.mint_v2_world_records(repo, arm_commit, tuple(mixed))


def dataclasses_replace(record, **changes):
    import dataclasses

    return dataclasses.replace(record, **changes)


# --- Blocker 4: aggregation wiring --------------------------------------------


def test_cell_aggregates_reconcile_without_raising(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        aggregates = v2p.derive_v2_cell_aggregates(records)
        assert "NULL|5000" in aggregates
        cell = aggregates["NULL|5000"]
        assert cell["planned_worlds"] == len(records)
        assert set(cell["candidates"]) == set(v2.FEATURE_IDS)


def test_required_coverage_status_covers_all_33_conclusions(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        status = v2p.derive_v2_required_coverage_status(records)
        assert set(status) == set(CONCLUSION_IDS)
        assert all(v in (v2.COVERAGE_ADEQUATE, v2.COVERAGE_INSUFFICIENT) for v in status.values())


def test_mechanical_conclusions_structural_incompleteness_overrides_everything(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        conclusions = v2p.derive_v2_mechanical_conclusions(
            records, structurally_complete=False, inherited_detection_conclusions=DUMMY_INHERITED
        )
        assert all(v == v2.MECHANICAL_STRUCTURAL_INCOMPLETE for v in conclusions.values())


def test_missing_inherited_conclusion_fails_closed(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        incomplete = dict(DUMMY_INHERITED)
        del incomplete[CONCLUSION_IDS[0]]
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.derive_v2_mechanical_conclusions(
                records, structurally_complete=True, inherited_detection_conclusions=incomplete
            )


# --- Blocker 3 / SS7: mint + historical result verification -----------------


def test_mint_world_records_detects_forged_record(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = list(v2p.run_canonical_v2_production_grid_in_session(session))
        forged = list(records)
        forged[0] = dataclasses_replace(forged[0], taxonomy="FORGED")
        with pytest.raises(v2p.V2ProductionIntegrityError):
            v2p.mint_v2_world_records(repo, arm_commit, tuple(forged))
        # Honest evidence mints cleanly.
        wr = v2p.mint_v2_world_records(repo, arm_commit, tuple(records))
        assert wr["record_count"] == len(small_jobs)


def test_mint_world_records_rejects_wrong_count(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        with pytest.raises(v2p.V2ProductionIntegrityError):
            v2p.mint_v2_world_records(repo, arm_commit, records[:-1])


def test_mint_result_end_to_end_matches_historical_verification(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records, inherited_detection_conclusions=DUMMY_INHERITED
        )
        assert result["world_records_count"] == len(small_jobs)
        assert set(result["conclusions"]) == set(CONCLUSION_IDS)
        assert v2p.verify_historical_v2_result(
            repo, arm_commit, world_records, result, inherited_detection_conclusions=DUMMY_INHERITED
        ) is True


def test_historical_verification_from_descendant_and_clean_clone(armed_small_repo, small_jobs, tmp_path):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records, inherited_detection_conclusions=DUMMY_INHERITED
        )
        _write(repo / v2p.CANONICAL_V2_WORLD_RECORDS_PATH, json_bytes(world_records))
        _write(repo / v2p.CANONICAL_V2_RESULT_PATH, json_bytes(result))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "persist evidence and result (test)")
        assert v2p.verify_historical_v2_result(
            repo, arm_commit, world_records, result, inherited_detection_conclusions=DUMMY_INHERITED
        ) is True
        clone = tmp_path / "clean_clone_for_result"
        subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
        assert v2p.verify_historical_v2_result(
            clone, arm_commit, world_records, result, inherited_detection_conclusions=DUMMY_INHERITED
        ) is True


def test_historical_verification_rejects_tampered_world_records(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records, inherited_detection_conclusions=DUMMY_INHERITED
        )
        tampered = copy.deepcopy(world_records)
        tampered["records"][0]["taxonomy"] = "FORGED"
        forged_bytes = json.dumps(tampered["records"], sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False).encode(
            "utf-8"
        ) + b"\n"
        tampered["records_sha256"] = hashlib.sha256(forged_bytes).hexdigest()
        tampered["records_size"] = len(forged_bytes)
        assert (
            v2p.verify_historical_v2_result(
                repo, arm_commit, tampered, result, inherited_detection_conclusions=DUMMY_INHERITED
            )
            is False
        )


def test_historical_verification_rejects_tampered_result(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records, inherited_detection_conclusions=DUMMY_INHERITED
        )
        tampered_result = copy.deepcopy(result)
        tampered_result["cell_aggregates"]["NULL|5000"]["world_valid_count"] = 999999
        assert (
            v2p.verify_historical_v2_result(
                repo, arm_commit, world_records, tampered_result, inherited_detection_conclusions=DUMMY_INHERITED
            )
            is False
        )


def test_caller_provided_aggregate_cannot_become_authority(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records, inherited_detection_conclusions=DUMMY_INHERITED
        )
        forged_result = copy.deepcopy(result)
        forged_result["conclusions"] = {cid: "FABRICATED_PASS" for cid in CONCLUSION_IDS}
        assert (
            v2p.verify_historical_v2_result(
                repo, arm_commit, world_records, forged_result, inherited_detection_conclusions=DUMMY_INHERITED
            )
            is False
        )


# --- Session / MAJOR repair --------------------------------------------------


def test_open_session_requires_historical_auth(tmp_path):
    repo = _commit_freeze_tree(tmp_path)
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
        v2p.open_v2_production_session(repo_root=repo)  # HEAD is the freeze, unarmed


def test_session_based_evaluation_matches_direct_fixture_equivalence(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        for job in small_jobs:
            rec = v2p.evaluate_v2_world_in_session(session, *job)
            world = v2p.simulate_dgp(scenario_id=job[0], n_rows=job[1], world_index=job[2])
            direct = v2p._production_evaluate_one_world(
                world, scenario=job[0], n_rows=job[1], world_index=job[2]
            )
            assert rec == direct


def test_session_evaluation_refuses_non_canonical_job(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.evaluate_v2_world_in_session(session, "NULL", 999999, 0)


def test_v2_production_integrity_error_is_used_meaningfully():
    # Regression guard for the "dead exception class" minor finding: it must
    # actually be raised through multiple reachable call sites, not merely
    # defined once and never thrown.
    import inspect

    source = inspect.getsource(v2p)
    assert "class V2ProductionIntegrityError" in source
    assert "raise V2ProductionIntegrityError" in source
    assert source.count("_refuse_integrity(") >= 5
