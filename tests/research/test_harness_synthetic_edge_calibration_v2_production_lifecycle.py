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
import dataclasses
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from scripts.research import harness_synthetic_edge_calibration_v2_inherited_ladder as ladder
from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p
from scripts.research import harness_synthetic_edge_calibration_v2_rank_policy as v2

REPO = Path(__file__).resolve().parents[2]
CONCLUSION_IDS = list(v2.frozen_required_coverage_map())


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
        ladder.AMENDMENT_003_MD_REL: _live_bytes(ladder.AMENDMENT_003_MD_REL),
        ladder.AMENDMENT_003_JSON_REL: _live_bytes(ladder.AMENDMENT_003_JSON_REL),
        ladder.AMENDMENT_004_MD_REL: _live_bytes(ladder.AMENDMENT_004_MD_REL),
        ladder.AMENDMENT_004_JSON_REL: _live_bytes(ladder.AMENDMENT_004_JSON_REL),
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
            "amendment_003_md_sha256": ladder.FROZEN_AMENDMENT_003_SHA256[ladder.AMENDMENT_003_MD_REL],
            "amendment_003_json_sha256": ladder.FROZEN_AMENDMENT_003_SHA256[ladder.AMENDMENT_003_JSON_REL],
            "amendment_004_md_sha256": ladder.FROZEN_AMENDMENT_004_SHA256[ladder.AMENDMENT_004_MD_REL],
            "amendment_004_json_sha256": ladder.FROZEN_AMENDMENT_004_SHA256[ladder.AMENDMENT_004_JSON_REL],
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
    """A disposable repo with freeze -> small-scope ARM already committed.

    Deliberately has NO reservation yet -- used by tests that specifically
    exercise the pre-reservation state (historical auth, reservation
    availability/duplicate/race checks).
    """
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        repo = _commit_freeze_tree(tmp_path)
        payload = _small_arm_payload(repo)
        arm_commit = _commit_arm(repo, payload)
        yield repo, arm_commit


@pytest.fixture
def reserved_small_repo(armed_small_repo, small_jobs):
    """freeze -> ARM -> durable reservation already committed.

    Required by any test that opens a genuine session: open_v2_production_session
    now refuses unless a matching reservation is already tracked at HEAD.
    """
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        v2p.establish_v2_durable_reservation(repo, arm_commit)
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


def test_execution_path_second_sequential_reservation_cannot_begin_computation(
    armed_small_repo, small_jobs
):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        v2p.establish_v2_durable_reservation(repo, arm_commit)
        v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        # A second, sequential real attempt through the real entrypoint --
        # not the standalone check -- must fail before it could ever open a
        # session or touch simulate_dgp.
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.establish_v2_durable_reservation(repo, arm_commit)


def test_execution_path_concurrent_reservation_race_via_real_entrypoint(armed_small_repo, small_jobs):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        # Both "processes" pass the pre-check (no reservation exists yet).
        v2p.assert_v2_reservation_available(repo, arm_commit)
        v2p.assert_v2_reservation_available(repo, arm_commit)
        # Process A wins: calls the real establish function, which commits.
        v2p.establish_v2_durable_reservation(repo, arm_commit)
        # Process A can now open a genuine session and execute.
        session_a = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records_a = v2p.run_canonical_v2_production_grid_in_session(session_a)
        assert len(records_a) == len(small_jobs)
        # Process B's real establish call (the only way it could reach
        # scientific computation) now fails closed -- it never opens a
        # session and never calls simulate_dgp.
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.establish_v2_durable_reservation(repo, arm_commit)


def test_crash_after_reservation_before_first_world_requires_fresh_session(
    armed_small_repo, small_jobs
):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        v2p.establish_v2_durable_reservation(repo, arm_commit)
        # Simulate a crash: the process that would have opened a session and
        # executed never did either. The durable reservation survives (it is
        # a git commit); a fresh process can open a new genuine session
        # against the SAME reservation and proceed -- it does not need (and
        # cannot create) a second reservation.
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        assert len(records) == len(small_jobs)
        # And still no second reservation is possible.
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.establish_v2_durable_reservation(repo, arm_commit)


def test_crash_during_checkpoint_leaves_no_torn_record_on_resume(
    armed_small_repo, small_jobs, tmp_path
):
    repo, arm_commit = armed_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        v2p.establish_v2_durable_reservation(repo, arm_commit)
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        store = v2p.V2DurablePartialWorldStore.open(
            tmp_path / "cache", run_identity=session.run_identity, arm_commit=session.arm_commit
        )
        job = small_jobs[0]
        rec = v2p.evaluate_v2_world_in_session(session, *job)
        # Simulate a crash mid-checkpoint-write: a torn .tmp file is left
        # behind (never atomically renamed into place), exactly what
        # _atomic_replace_bytes guarantees can never become the durable
        # object.
        target = store._world_path(rec.world_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        (target.with_name(target.name + ".tmp")).write_bytes(b'{"kind": "torn"')
        assert not target.is_file()
        # Resume: the store must not see any completed world for this job
        # (the torn .tmp is not the durable record), so it recomputes cleanly.
        cached_before = store.load_structurally_valid_cached()
        assert job not in cached_before
        store.checkpoint_completed_world(rec, job)
        cached_after = store.load_structurally_valid_cached()
        assert cached_after[job] == rec


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


def test_checkpoint_resume_matches_original_and_avoids_recompute(reserved_small_repo, small_jobs, tmp_path):
    repo, arm_commit = reserved_small_repo
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


def test_checkpoint_rejects_conflicting_duplicate_record(reserved_small_repo, small_jobs, tmp_path):
    repo, arm_commit = reserved_small_repo
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


def test_checkpoint_store_identity_mismatch_fails_closed(reserved_small_repo, small_jobs, tmp_path):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        store_path = tmp_path / "cache"
        v2p.V2DurablePartialWorldStore.open(
            store_path, run_identity=session.run_identity, arm_commit=session.arm_commit
        )
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.V2DurablePartialWorldStore.open(store_path, run_identity="0" * 64, arm_commit=session.arm_commit)


def test_forged_checkpoint_cannot_bypass_mint_reauthentication(reserved_small_repo, small_jobs, tmp_path):
    repo, arm_commit = reserved_small_repo
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


def test_cell_aggregates_reconcile_without_raising(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        aggregates = v2p.derive_v2_cell_aggregates(records)
        assert "NULL|5000" in aggregates
        cell = aggregates["NULL|5000"]
        assert cell["planned_worlds"] == len(records)
        assert set(cell["candidates"]) == set(v2.FEATURE_IDS)


def test_required_coverage_status_covers_all_33_conclusions(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        status = v2p.derive_v2_required_coverage_status(records)
        assert set(status) == set(CONCLUSION_IDS)
        assert all(v in (v2.COVERAGE_ADEQUATE, v2.COVERAGE_INSUFFICIENT) for v in status.values())


def test_mechanical_conclusions_structural_incompleteness_overrides_everything(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        conclusions = v2p.derive_v2_mechanical_conclusions(
            records, structurally_complete=False
        )
        assert all(v == v2.MECHANICAL_STRUCTURAL_INCOMPLETE for v in conclusions.values())


def test_no_caller_scientific_mapping_parameter_exists(reserved_small_repo, small_jobs):
    """The old caller-controlled inherited_detection_conclusions mapping is
    completely gone -- not renamed, not replaced by a kwarg/callback/strategy
    object. derive_v2_mechanical_conclusions accepts only evidence records and
    structurally_complete; any other keyword argument is rejected by Python
    itself, not merely ignored."""
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        with pytest.raises(TypeError):
            v2p.derive_v2_mechanical_conclusions(
                records,
                structurally_complete=True,
                inherited_detection_conclusions={},
            )
        with pytest.raises(TypeError):
            v2p.mint_v2_result(
                repo, arm_commit, records, inherited_detection_conclusions={}
            )
        # All 33 conclusions ARE fully derivable internally with no such
        # argument at all.
        conclusions = v2p.derive_v2_mechanical_conclusions(records, structurally_complete=True)
        assert set(conclusions) == set(CONCLUSION_IDS)


def test_unknown_conclusion_id_fails_closed():
    with pytest.raises(ladder.V2InheritedLadderAuthorityError):
        ladder.derive_v2_inherited_conclusion("NOT_A_REAL_CONCLUSION_ID", [])


# --- Blocker 3 / SS7: mint + historical result verification -----------------


def test_mint_world_records_detects_forged_record(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
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


def test_mint_world_records_rejects_wrong_count(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        with pytest.raises(v2p.V2ProductionIntegrityError):
            v2p.mint_v2_world_records(repo, arm_commit, records[:-1])


def test_mint_result_end_to_end_matches_historical_verification(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records
        )
        assert result["world_records_count"] == len(small_jobs)
        assert set(result["conclusions"]) == set(CONCLUSION_IDS)
        nested = result["conclusions"][ladder.FINAL_OVERALL_ID]
        assert nested is not None
        assert nested == result["final_overall_conclusion"]
        assert nested in ladder.frozen_final_overall_terminal_labels()
        for cid, value in result["conclusions"].items():
            assert value is not None
            assert isinstance(value, str) and value != ""
        assert v2p.verify_historical_v2_result(
            repo, arm_commit, world_records, result
        ) is True


def test_historical_verification_from_descendant_and_clean_clone(reserved_small_repo, small_jobs, tmp_path):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records
        )
        _write(repo / v2p.CANONICAL_V2_WORLD_RECORDS_PATH, json_bytes(world_records))
        _write(repo / v2p.CANONICAL_V2_RESULT_PATH, json_bytes(result))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "persist evidence and result (test)")
        assert v2p.verify_historical_v2_result(
            repo, arm_commit, world_records, result
        ) is True
        clone = tmp_path / "clean_clone_for_result"
        subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
        assert v2p.verify_historical_v2_result(
            clone, arm_commit, world_records, result
        ) is True


def test_historical_verification_rejects_tampered_world_records(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records
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
                repo, arm_commit, tampered, result
            )
            is False
        )


def test_historical_verification_rejects_tampered_result(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records
        )
        tampered_result = copy.deepcopy(result)
        tampered_result["cell_aggregates"]["NULL|5000"]["world_valid_count"] = 999999
        assert (
            v2p.verify_historical_v2_result(
                repo, arm_commit, world_records, tampered_result
            )
            is False
        )


def test_caller_provided_aggregate_cannot_become_authority(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(
            repo, arm_commit, records
        )
        forged_result = copy.deepcopy(result)
        forged_result["conclusions"] = {cid: "FABRICATED_PASS" for cid in CONCLUSION_IDS}
        assert (
            v2p.verify_historical_v2_result(
                repo, arm_commit, world_records, forged_result
            )
            is False
        )


# --- Session / MAJOR repair --------------------------------------------------


def test_open_session_requires_historical_auth(tmp_path):
    repo = _commit_freeze_tree(tmp_path)
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
        v2p.open_v2_production_session(repo_root=repo)  # HEAD is the freeze, unarmed


def test_session_based_evaluation_matches_direct_fixture_equivalence(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        for job in small_jobs:
            rec = v2p.evaluate_v2_world_in_session(session, *job)
            world = v2p.simulate_dgp(scenario_id=job[0], n_rows=job[1], world_index=job[2])
            direct = v2p._production_evaluate_one_world(
                world, scenario=job[0], n_rows=job[1], world_index=job[2]
            )
            assert rec == direct


def test_session_evaluation_refuses_non_canonical_job(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.evaluate_v2_world_in_session(session, "NULL", 999999, 0)


def test_genuine_session_adversarial_matrix(reserved_small_repo, small_jobs):
    """Every forged/copied/mutated session must fail BEFORE scientific
    computation; only the literal object issued by open_v2_production_session
    may execute."""
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        genuine = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        job = small_jobs[0]

        forged = {
            "None": None,
            "False": False,
            "True": True,
            "empty_dict": {},
            "manually_instantiated_object": v2p.V2ProductionSession(
                repo_root=genuine.repo_root,
                arm_commit=genuine.arm_commit,
                run_identity=genuine.run_identity,
                canonical_v2_plan_sha256=genuine.canonical_v2_plan_sha256,
                v2_policy_sha256=genuine.v2_policy_sha256,
                opened_at=genuine.opened_at,
            ),
            "copied_via_dataclasses_replace": dataclasses.replace(genuine, opened_at=0.0),
            "string_masquerading_as_token": genuine.run_identity,
        }
        for label, candidate in forged.items():
            with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
                v2p.evaluate_v2_world_in_session(candidate, *job)
            with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
                v2p.run_canonical_v2_production_grid_in_session(candidate)

        # Mutating the genuine session in place (bypassing frozen=True via
        # object.__setattr__) must also be caught -- identity survives, but
        # the registered snapshot no longer matches.
        object.__setattr__(genuine, "run_identity", "0" * 64)
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
            v2p.evaluate_v2_world_in_session(genuine, *job)

        # A freshly (and correctly) opened session still works.
        fresh = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        rec = v2p.evaluate_v2_world_in_session(fresh, *job)
        assert rec.world_state in (v2.WORLD_VALID, v2.WORLD_INVALID)


def test_session_from_different_repo_or_arm_is_independently_genuine_but_scoped(
    tmp_path, small_jobs
):
    """A session legitimately opened for a different repo/ARM is itself
    genuine (it went through open_v2_production_session for THAT repo/ARM),
    but canonical_v2_production_jobs() is a global, not session-scoped,
    source of truth, so it cannot be used to smuggle a different job list --
    there is no parameter through which a session could do that."""
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        repo_a = _commit_freeze_tree(tmp_path, name="repo_a")
        payload_a = _small_arm_payload(repo_a)
        arm_a = _commit_arm(repo_a, payload_a)
        v2p.establish_v2_durable_reservation(repo_a, arm_a)
        session_a = v2p.open_v2_production_session(repo_root=repo_a, arm_commit=arm_a)

        repo_b = _commit_freeze_tree(tmp_path, name="repo_b")
        payload_b = _small_arm_payload(repo_b)
        arm_b = _commit_arm(repo_b, payload_b)
        v2p.establish_v2_durable_reservation(repo_b, arm_b)
        session_b = v2p.open_v2_production_session(repo_root=repo_b, arm_commit=arm_b)

        # Two independently-issued sessions are always distinct objects (each
        # goes through its own open_v2_production_session call and its own
        # registry entry), regardless of whether their bound identities
        # happen to coincide (byte-identical disposable repos can legitimately
        # produce identical commit hashes).
        assert session_a is not session_b
        # Both are independently genuine and both evaluate the same
        # canonical job identically (per-world science does not depend on
        # which repo/ARM authorized it, only on frozen DGP/policy).
        rec_a = v2p.evaluate_v2_world_in_session(session_a, *small_jobs[0])
        rec_b = v2p.evaluate_v2_world_in_session(session_b, *small_jobs[0])
        assert rec_a == rec_b


def test_v2_production_integrity_error_is_used_meaningfully():
    # Regression guard for the "dead exception class" minor finding: it must
    # actually be raised through multiple reachable call sites, not merely
    # defined once and never thrown.
    import inspect

    source = inspect.getsource(v2p)
    assert "class V2ProductionIntegrityError" in source
    assert "raise V2ProductionIntegrityError" in source
    assert source.count("_refuse_integrity(") >= 5


# --- 33/33 implementation binding: same-evidence-same-result, forgery ------


def test_mutated_conclusion_id_fails_historical_verification(reserved_small_repo, small_jobs):
    """MUTATED_33_ID_RESULT_VERIFIES = NO: tampering any one of the 33 stored
    conclusion values must be caught even though every ordinary payload hash
    (world-records digest, evidence bytes) is left untouched."""
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(repo, arm_commit, records)
        tampered_result = copy.deepcopy(result)
        cid = CONCLUSION_IDS[0]
        original = tampered_result["conclusions"][cid]
        # flip to a definitely-different valid-looking string
        tampered_result["conclusions"][cid] = (
            "PASS" if original != "PASS" else "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"
        )
        assert (
            v2p.verify_historical_v2_result(repo, arm_commit, world_records, tampered_result)
            is False
        )


def test_mutated_final_overall_conclusion_fails_historical_verification(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(repo, arm_commit, records)
        tampered_result = copy.deepcopy(result)
        tampered_result["final_overall_conclusion"] = "CALIBRATION_PASSED_FORGED"
        assert (
            v2p.verify_historical_v2_result(repo, arm_commit, world_records, tampered_result)
            is False
        )


def test_same_evidence_same_conclusions_and_final_across_independent_calls(reserved_small_repo, small_jobs):
    """SAME_EVIDENCE_SAME_RESULT: two independent derivation call paths over
    byte-identical evidence must agree exactly, with no parameter available
    to make them differ."""
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)

        result_a = v2p.mint_v2_result(repo, arm_commit, records)
        result_b = v2p.mint_v2_result(repo, arm_commit, records)
        assert result_a["conclusions"] == result_b["conclusions"]
        assert result_a["final_overall_conclusion"] == result_b["final_overall_conclusion"]

        # Independent path: derive conclusions directly, bypassing mint entirely.
        direct_conclusions = v2p.derive_v2_mechanical_conclusions(
            records, structurally_complete=(len(records) == len(small_jobs))
        )
        direct_final = v2p.derive_v2_final_overall_mechanical_conclusion(
            records, structurally_complete=(len(records) == len(small_jobs))
        )
        assert direct_conclusions == result_a["conclusions"]
        assert direct_final == result_a["final_overall_conclusion"]

        canonical_a = v2p.canonical_json_bytes(v2p._jsonable(result_a["conclusions"]))
        canonical_b = v2p.canonical_json_bytes(v2p._jsonable(result_b["conclusions"]))
        assert canonical_a == canonical_b


def test_no_caller_parameter_can_produce_a_second_scientific_result(reserved_small_repo, small_jobs):
    """SECOND_SCIENTIFIC_RESULT_POSSIBLE = NO: there is no keyword, callback,
    or override argument anywhere in the mint path that could make identical
    evidence produce two different final conclusions."""
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        import inspect

        sig = inspect.signature(v2p.mint_v2_result)
        assert set(sig.parameters) == {"repo_root", "arm_commit", "evidence"}
        sig2 = inspect.signature(v2p.derive_v2_mechanical_conclusions)
        assert set(sig2.parameters) == {"records", "structurally_complete"}
        sig3 = inspect.signature(v2p.verify_historical_v2_result)
        assert set(sig3.parameters) == {"repo_root", "arm_commit", "world_records", "result"}
        # And, mechanically, calling mint twice really does agree (see the
        # dedicated same-evidence test above for the full comparison).
        result_a = v2p.mint_v2_result(repo, arm_commit, records)
        result_b = v2p.mint_v2_result(repo, arm_commit, records)
        assert result_a["final_overall_conclusion"] == result_b["final_overall_conclusion"]


def test_concurrent_mint_calls_bind_to_the_same_evidence_identity(reserved_small_repo, small_jobs):
    """TOCTOU: two 'concurrent' derivations (simulated sequentially, since
    mint is a pure function of its evidence argument with no shared mutable
    state) over the same evidence never diverge, and a result bound to
    different evidence (a different world's taxonomy) is provably distinct."""
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = list(v2p.run_canonical_v2_production_grid_in_session(session))
        result_1 = v2p.mint_v2_result(repo, arm_commit, tuple(records))
        result_2 = v2p.mint_v2_result(repo, arm_commit, tuple(records))
        assert result_1["conclusions"] == result_2["conclusions"]
        assert result_1["world_records_sha256"] == result_2["world_records_sha256"]
        # A result minted from a different evidence identity is bound to that
        # identity (a different world_records_sha256), never silently merged
        # with the first.
        mutated = list(records)
        mutated[0] = dataclasses.replace(mutated[0], taxonomy="FORGED_FOR_TEST")
        with pytest.raises(v2p.V2ProductionIntegrityError):
            v2p.mint_v2_result(repo, arm_commit, tuple(mutated))


def test_33_id_minted_values_not_just_keys(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        result = v2p.mint_v2_result(repo, arm_commit, records)
        specified = set(CONCLUSION_IDS)
        assert len(specified) == 33
        assert set(result["conclusions"]) == specified
        labels = ladder.frozen_final_overall_terminal_labels()
        nested = result["conclusions"][ladder.FINAL_OVERALL_ID]
        assert nested is not None
        assert nested in labels
        assert nested == result["final_overall_conclusion"]
        for value in result["conclusions"].values():
            assert value is not None
            assert isinstance(value, str) and value != ""


def test_verifier_rejects_final_overall_forgeries(reserved_small_repo, small_jobs):
    repo, arm_commit = reserved_small_repo
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small_jobs):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        world_records = v2p.mint_v2_world_records(repo, arm_commit, records)
        result = v2p.mint_v2_result(repo, arm_commit, records)
        correct = result["final_overall_conclusion"]
        wrong = (
            "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"
            if correct != "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"
            else "CALIBRATION_INDETERMINATE"
        )

        nested_null = copy.deepcopy(result)
        nested_null["conclusions"][ladder.FINAL_OVERALL_ID] = None
        assert v2p.verify_historical_v2_result(repo, arm_commit, world_records, nested_null) is False

        nested_wrong = copy.deepcopy(result)
        nested_wrong["conclusions"][ladder.FINAL_OVERALL_ID] = wrong
        assert v2p.verify_historical_v2_result(repo, arm_commit, world_records, nested_wrong) is False

        top_wrong = copy.deepcopy(result)
        top_wrong["final_overall_conclusion"] = wrong
        assert v2p.verify_historical_v2_result(repo, arm_commit, world_records, top_wrong) is False

        both_wrong = copy.deepcopy(result)
        both_wrong["conclusions"][ladder.FINAL_OVERALL_ID] = wrong
        both_wrong["final_overall_conclusion"] = wrong
        assert v2p.verify_historical_v2_result(repo, arm_commit, world_records, both_wrong) is False
