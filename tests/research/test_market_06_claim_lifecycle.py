"""CLAIM -> RESERVATION -> ARM -> FREEZE lifecycle (red-team L10/L11/L12).

Real temporary Git repositories. No live ARM/reservation/claim/RESULT is
created in this repository, and no canonical execution is run on retained
data: the scientific step is always stubbed with synthetic values.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.research import market_06_canonical_reconstruction as recon
from scripts.research import market_06_execution_lifecycle as lifecycle
from scripts.research import market_06_git_authority as gitauth
from scripts.research import market_06_result_persistence as persistence

REPO = Path(__file__).resolve().parents[2]
FREEZE_REL = "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.json"


def _run(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", *args],
        cwd=repo, capture_output=True, check=True,
    )
    return proc.stdout.decode().strip()


def _commit(repo: Path, message: str) -> str:
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", message)
    return _run(repo, "rev-parse", "HEAD")


def _freeze_payload(impl_head, impl_tree, module_sha):
    return {
        "research_id": lifecycle.RESEARCH_ID,
        "implementation_head": impl_head,
        "implementation_tree": impl_tree,
        "module_sha256": module_sha,
        "prereg_authority": {
            "prereg_freeze_head": lifecycle.PREREG_FREEZE_HEAD,
            "prereg_freeze_tree": lifecycle.PREREG_FREEZE_TREE,
            "prereg_content_head": lifecycle.PREREG_CONTENT_HEAD,
        },
        "data_authority": {
            "dataset_id": lifecycle.DATASET_ID,
            "snapshot_id": lifecycle.SNAPSHOT_ID,
            "durable_evidence_root_sha256": lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        },
    }


def _arm_payload(freeze_head, freeze_tree, run_identity):
    return {
        "research_id": lifecycle.RESEARCH_ID,
        "prereg_freeze_head": lifecycle.PREREG_FREEZE_HEAD,
        "prereg_freeze_tree": lifecycle.PREREG_FREEZE_TREE,
        "implementation_freeze_head": freeze_head,
        "implementation_freeze_tree": freeze_tree,
        "implementation_freeze_relpath": FREEZE_REL,
        "implementation_module_root": "scripts/research/",
        "dataset_id": lifecycle.DATASET_ID,
        "snapshot_id": lifecycle.SNAPSHOT_ID,
        "durable_evidence_root_sha256": lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        "run_identity": run_identity,
        "authorization_kind": lifecycle.AUTHORIZATION_KIND,
        "one_shot": True,
        "scientific_outcomes_inspected_before_arm": False,
        "protected_2025_opened": False,
        "protected_2026_opened": False,
    }


def _reservation_payload(arm_commit, freeze_head, freeze_tree, run_identity, **over):
    payload = {
        "research_id": lifecycle.RESEARCH_ID,
        "run_identity": over.pop("run_identity", run_identity),
        "arm_commit": arm_commit,
        "implementation_freeze_head": freeze_head,
        "implementation_freeze_tree": freeze_tree,
        "dataset_id": lifecycle.DATASET_ID,
        "snapshot_id": lifecycle.SNAPSHOT_ID,
        "durable_evidence_root_sha256": lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        "authorization_kind": lifecycle.AUTHORIZATION_KIND,
        "result_target_paths": [lifecycle.RESULT_JSON_REL, lifecycle.RESULT_MD_REL],
        "claim_target_path": lifecycle.CLAIM_JSON_REL,
        "consumed": False,
        "scientific_outcomes_inspected_before_reservation": False,
        "protected_2025_opened": False,
        "protected_2026_opened": False,
    }
    payload.update(over)
    return payload


def _claim_payload(arm_commit, reservation_commit, freeze_head, freeze_tree,
                   run_identity, **over):
    payload = {
        "research_id": lifecycle.RESEARCH_ID,
        "run_identity": over.pop("run_identity", run_identity),
        "arm_commit": arm_commit,
        "reservation_commit": reservation_commit,
        "implementation_freeze_head": freeze_head,
        "implementation_freeze_tree": freeze_tree,
        "dataset_id": lifecycle.DATASET_ID,
        "snapshot_id": lifecycle.SNAPSHOT_ID,
        "durable_evidence_root_sha256": lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        "claim_state": lifecycle.CLAIM_STATE_CLAIMED,
        "result_target_paths": [lifecycle.RESULT_JSON_REL, lifecycle.RESULT_MD_REL],
        "protected_2025_opened": False,
        "protected_2026_opened": False,
    }
    payload.update(over)
    return payload


@pytest.fixture
def chain(tmp_path, monkeypatch):
    """Builds F -> A -> R, and returns helpers to add C."""

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q", "-b", "main")
    for rel in lifecycle.SCIENTIFIC_MODULE_RELPATHS:
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dst)
    (repo / "docs/research").mkdir(parents=True, exist_ok=True)
    impl_head = _commit(repo, "implementation")
    impl_tree = _run(repo, "rev-parse", "HEAD^{tree}")

    monkeypatch.setattr(gitauth, "repo_root", lambda: repo)
    module_sha = lifecycle.live_module_sha256()
    run_identity = lifecycle.derive_run_identity(module_sha)

    (repo / FREEZE_REL).write_text(
        json.dumps(_freeze_payload(impl_head, impl_tree, module_sha), indent=2))
    freeze_head = _commit(repo, "freeze")
    freeze_tree = _run(repo, "rev-parse", "HEAD^{tree}")

    (repo / lifecycle.ARM_JSON_REL).write_text(
        json.dumps(_arm_payload(freeze_head, freeze_tree, run_identity), indent=2))
    arm_commit = _commit(repo, "arm")

    def add_reservation(**over):
        identity = over.pop("run_identity", run_identity)
        (repo / lifecycle.RESERVATION_JSON_REL).write_text(json.dumps(
            _reservation_payload(arm_commit, freeze_head, freeze_tree,
                                 identity, **over), indent=2))
        return _commit(repo, "reservation")

    def add_claim(reservation_commit, **over):
        identity = over.pop("run_identity", run_identity)
        (repo / lifecycle.CLAIM_JSON_REL).write_text(json.dumps(
            _claim_payload(arm_commit, reservation_commit, freeze_head,
                           freeze_tree, identity, **over), indent=2))
        return _commit(repo, "claim")

    return {
        "repo": repo, "impl_head": impl_head, "freeze_head": freeze_head,
        "freeze_tree": freeze_tree, "arm_commit": arm_commit,
        "run_identity": run_identity, "add_reservation": add_reservation,
        "add_claim": add_claim,
    }


# ==========================================================================
# 18. MANDATORY: F -> A -> R -> C with no self-referential commit SHA.
# ==========================================================================


def test_full_chain_resolves_without_any_self_referential_commit_sha(chain):
    reservation_commit = chain["add_reservation"]()
    claim_commit = chain["add_claim"](reservation_commit)

    authority = lifecycle.verify_claim_from_commit(claim_commit)

    assert authority.claim_commit == claim_commit
    assert authority.reservation_commit == reservation_commit
    assert authority.arm_commit == chain["arm_commit"]
    assert authority.permit.implementation_freeze_head == chain["freeze_head"]
    assert authority.run_identity == chain["run_identity"]

    # HEAD == C resolves the same chain with nothing passed in
    resolved = lifecycle.resolve_canonical_authority()
    assert resolved.claim_commit == claim_commit

    # no artifact contains its own commit SHA
    repo = chain["repo"]
    reservation = json.loads((repo / lifecycle.RESERVATION_JSON_REL).read_text())
    claim = json.loads((repo / lifecycle.CLAIM_JSON_REL).read_text())
    assert reservation_commit not in json.dumps(reservation)
    assert claim_commit not in json.dumps(claim)
    for field in lifecycle.SELF_REFERENTIAL_FIELDS:
        assert field not in reservation
        assert field not in claim
    # the reservation does name its ARM, and the claim names its reservation
    assert reservation["arm_commit"] == chain["arm_commit"]
    assert claim["reservation_commit"] == reservation_commit


def test_reservation_carrying_its_own_sha_is_refused(chain):
    reservation_commit = chain["add_reservation"]()
    repo = chain["repo"]
    payload = json.loads((repo / lifecycle.RESERVATION_JSON_REL).read_text())
    payload["reservation_commit_sha"] = reservation_commit
    (repo / lifecycle.RESERVATION_JSON_REL).write_text(json.dumps(payload))
    mutated = _commit(repo, "self-referential reservation")
    with pytest.raises(lifecycle.Market06LifecycleError):
        lifecycle.verify_execution_reservation_from_commit(mutated)


def test_arm_is_never_inferred_from_head(chain):
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.verify_execution_arm()
    assert "ARM_COMMIT_REQUIRED" in str(exc.value)


def test_arm_must_precede_reservation_and_reservation_precede_claim(chain):
    reservation_commit = chain["add_reservation"]()
    claim_commit = chain["add_claim"](reservation_commit)
    assert gitauth.is_ancestor(chain["arm_commit"], reservation_commit)
    assert gitauth.is_ancestor(reservation_commit, claim_commit)
    # claim pointing at a reservation commit that is NOT its ancestor
    with pytest.raises((lifecycle.Market06ExecutionNotAuthorized,
                        lifecycle.Market06LifecycleError,
                        gitauth.Market06GitAuthorityError)):
        lifecycle.verify_claim_from_commit(reservation_commit)


# ==========================================================================
# 19. ONE-SHOT CASES A-G.
# ==========================================================================


def test_case_a_reservation_without_claim_refuses_science(chain):
    reservation_commit = chain["add_reservation"]()
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.verify_claim_from_commit(reservation_commit)
    assert "NO_TRACKED_CLAIM" in str(exc.value)


def test_case_b_full_chain_is_accepted(chain):
    claim_commit = chain["add_claim"](chain["add_reservation"]())
    assert lifecycle.verify_claim_from_commit(claim_commit).run_identity == chain["run_identity"]


def test_case_c_claim_without_result_allows_first_invocation(chain, monkeypatch):
    claim_commit = chain["add_claim"](chain["add_reservation"]())
    authority = lifecycle.verify_claim_from_commit(claim_commit)
    lifecycle.assert_shot_not_already_consumed(authority.run_identity)
    lifecycle.record_execution_attempt(authority)
    ledger = lifecycle.read_attempt_ledger()
    assert authority.run_identity in ledger
    assert ledger[authority.run_identity]["claim_state"] == lifecycle.CLAIM_STATE_CLAIMED


def test_case_d_second_claim_for_same_run_identity_refused(chain):
    reservation_commit = chain["add_reservation"]()
    claim_commit = chain["add_claim"](reservation_commit)
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.assert_claim_creatable(chain["run_identity"], commit=claim_commit)
    assert "ALREADY_CLAIMED" in str(exc.value)


def test_case_e_crash_before_result_still_consumes_the_shot(chain):
    claim_commit = chain["add_claim"](chain["add_reservation"]())
    authority = lifecycle.verify_claim_from_commit(claim_commit)

    # first invocation: consume, then simulate a crash before RESULT
    lifecycle.record_execution_attempt(authority)
    with pytest.raises(RuntimeError):
        raise RuntimeError("simulated crash after outcome, before result commit")

    # no RESULT exists, yet a second run is refused
    assert not (chain["repo"] / lifecycle.RESULT_JSON_REL).exists()
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.assert_shot_not_already_consumed(authority.run_identity)
    assert "ALREADY_CLAIMED" in str(exc.value)
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        lifecycle.record_execution_attempt(authority)


def test_case_f_result_present_refuses_later_execution(chain):
    reservation_commit = chain["add_reservation"]()
    claim_commit = chain["add_claim"](reservation_commit)
    repo = chain["repo"]
    (repo / lifecycle.RESULT_JSON_REL).write_text(
        json.dumps({"run_identity": chain["run_identity"], "classification": "REDACTED"}))
    consumed = _commit(repo, "result")
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.verify_claim_from_commit(consumed)
    assert "ALREADY_CONSUMED" in str(exc.value)


def test_case_g_foreign_run_identity_cannot_reuse_authority(chain):
    reservation_commit = chain["add_reservation"](run_identity="0" * 64)
    with pytest.raises(lifecycle.Market06LifecycleError):
        lifecycle.verify_execution_reservation_from_commit(reservation_commit)


def test_claim_with_foreign_run_identity_refused(chain):
    reservation_commit = chain["add_reservation"]()
    claim_commit = chain["add_claim"](reservation_commit, run_identity="0" * 64)
    with pytest.raises(lifecycle.Market06LifecycleError):
        lifecycle.verify_claim_from_commit(claim_commit)


def test_claim_carrying_outcome_is_refused(chain):
    reservation_commit = chain["add_reservation"]()
    claim_commit = chain["add_claim"](reservation_commit, classification="PROMOTED")
    with pytest.raises(lifecycle.Market06LifecycleError) as exc:
        lifecycle.verify_claim_from_commit(claim_commit)
    assert "CARRIES_OUTCOME" in str(exc.value)


def test_consumed_reservation_refused(chain):
    reservation_commit = chain["add_reservation"](consumed=True)
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        lifecycle.verify_execution_reservation_from_commit(reservation_commit)


# ==========================================================================
# 20. RESULT determinism and staging.
# ==========================================================================


def _outcome(**over):
    payload = {
        "classification": "MARKET_06_NO_EVIDENCE",
        "gates": {"G1": True, "G2": False, "G3": True, "G4": False, "G5": False, "G6": True},
        "BETA_ABS_DISLOCATION_Z": 0.5, "BETA_ABS_DISLOCATION_Z_CI95_LOW": -0.1,
        "BETA_ABS_DISLOCATION_Z_CI95_HIGH": 1.1, "POOLED_MAE_BASELINE": 0.04,
        "POOLED_MAE_CANDIDATE": 0.039, "RELATIVE_MAE_IMPROVEMENT": 0.01,
        "RELATIVE_MAE_IMPROVEMENT_CI95_LOW": -0.01,
        "RELATIVE_MAE_IMPROVEMENT_CI95_HIGH": 0.03,
        "YEAR_2023_RELATIVE_MAE_IMPROVEMENT": 0.012,
        "YEAR_2024_RELATIVE_MAE_IMPROVEMENT": 0.008,
        "YEAR_2023_BASELINE_MAE": 0.041, "YEAR_2023_CANDIDATE_MAE": 0.0405,
        "YEAR_2024_BASELINE_MAE": 0.039, "YEAR_2024_CANDIDATE_MAE": 0.0387,
        "N_TRAIN": 330, "N_2023": 363, "N_2024": 364,
        "BASELINE_COLUMNS": ["INTERCEPT", "BTC_SIDE", "ABS_BTC_RET_24H_STD", "RV_BTC_24H_STD"],
        "CANDIDATE_COLUMNS": ["INTERCEPT", "BTC_SIDE", "ABS_BTC_RET_24H_STD",
                              "RV_BTC_24H_STD", "ABS_DISLOCATION_Z_STD"],
        "TRAIN_SD_CONVENTION": "numpy.std(x, ddof=0)",
        "BLOCK_LENGTH_DAYS": 14, "BOOTSTRAP_REPLICATES": 5000, "RANDOM_SEED": 2026092106,
    }
    payload.update(over)
    return payload


def _audit(run_identity):
    return {
        "run_identity": run_identity,
        "dataset_id": lifecycle.DATASET_ID,
        "snapshot_id": lifecycle.SNAPSHOT_ID,
        "binance_timestamps": 315648,
        "okx_timestamps": 315648,
        "okx_out_of_window_trimmed": 252,
        "interpolation": False,
    }


@pytest.fixture
def authority(chain):
    return lifecycle.verify_claim_from_commit(chain["add_claim"](chain["add_reservation"]()))


def test_result_bytes_are_deterministic(authority):
    a = persistence.stage_canonical_result(
        authority, _outcome(), _audit(authority.run_identity), write=False)
    b = persistence.stage_canonical_result(
        authority, _outcome(), _audit(authority.run_identity), write=False)
    assert a.json_bytes == b.json_bytes
    assert a.sha256 == b.sha256
    assert a.json_bytes.endswith(b"\n")


def test_changed_metric_changes_result_sha256(authority):
    base = persistence.stage_canonical_result(
        authority, _outcome(), _audit(authority.run_identity), write=False)
    changed = persistence.stage_canonical_result(
        authority, _outcome(RELATIVE_MAE_IMPROVEMENT=0.02),
        _audit(authority.run_identity), write=False)
    assert base.sha256 != changed.sha256


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_inf_rejected(authority, bad):
    with pytest.raises(persistence.Market06ResultError):
        persistence.stage_canonical_result(
            authority, _outcome(RELATIVE_MAE_IMPROVEMENT=bad),
            _audit(authority.run_identity), write=False)


def test_missing_gate_rejected(authority):
    gates = {"G1": True, "G2": True, "G3": True, "G4": True, "G5": True}
    with pytest.raises(persistence.Market06ResultError) as exc:
        persistence.stage_canonical_result(
            authority, _outcome(gates=gates), _audit(authority.run_identity), write=False)
    assert "GATE_MISSING" in str(exc.value)


def test_missing_metric_rejected(authority):
    outcome = _outcome()
    del outcome["N_2024"]
    with pytest.raises(persistence.Market06ResultError):
        persistence.stage_canonical_result(
            authority, outcome, _audit(authority.run_identity), write=False)


def test_wrong_run_identity_audit_rejected(authority):
    audit = _audit("0" * 64)
    with pytest.raises(persistence.Market06ResultError):
        persistence.stage_canonical_result(authority, _outcome(), audit, write=False)


def test_wrong_dataset_rejected(authority):
    audit = _audit(authority.run_identity)
    audit["dataset_id"] = "WRONG"
    with pytest.raises(persistence.Market06ResultError):
        persistence.stage_canonical_result(authority, _outcome(), audit, write=False)


def test_claim_authority_is_required(authority):
    with pytest.raises(persistence.Market06ResultError):
        persistence.stage_canonical_result(
            authority.permit, _outcome(), _audit(authority.run_identity), write=False)
    with pytest.raises(persistence.Market06ResultError):
        persistence.stage_canonical_result(
            {"run_identity": "x"}, _outcome(), _audit("x"), write=False)


def test_result_written_only_to_frozen_paths(authority, chain):
    staged = persistence.stage_canonical_result(
        authority, _outcome(), _audit(authority.run_identity))
    assert staged.json_path == lifecycle.RESULT_JSON_REL
    assert staged.md_path == lifecycle.RESULT_MD_REL
    assert (chain["repo"] / lifecycle.RESULT_JSON_REL).read_bytes() == staged.json_bytes
    # nondeterministic FIELD NAMES are absent from identity. Structural
    # counts such as "binance_timestamps" are legitimate and deterministic,
    # so this checks keys exactly rather than by substring.
    def _keys(node):
        if isinstance(node, dict):
            for key, item in node.items():
                yield key.lower()
                yield from _keys(item)
        elif isinstance(node, list):
            for item in node:
                yield from _keys(item)

    keys = set(_keys(staged.payload))
    assert not (keys & persistence.FORBIDDEN_PAYLOAD_KEYS)
    for key in keys - persistence.ALLOWED_KEY_EXCEPTIONS:
        assert not key.endswith(persistence.FORBIDDEN_KEY_SUFFIXES)
    assert "binance_timestamps" in keys  # legitimate structural count kept


def test_existing_result_prevents_new_staging(authority, chain):
    repo = chain["repo"]
    (repo / lifecycle.RESULT_JSON_REL).write_text(
        json.dumps({"run_identity": authority.run_identity}))
    _commit(repo, "existing result")
    # the claim commit now has a RESULT bound to this run identity
    fresh = lifecycle.ClaimAuthority(
        permit=authority.permit, reservation=authority.reservation,
        claim=authority.claim, arm_commit=authority.arm_commit,
        reservation_commit=authority.reservation_commit,
        claim_commit=_run(repo, "rev-parse", "HEAD"))
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        persistence.stage_canonical_result(
            fresh, _outcome(), _audit(authority.run_identity), write=False)


def test_result_payload_binds_full_authority_chain(authority):
    staged = persistence.stage_canonical_result(
        authority, _outcome(), _audit(authority.run_identity), write=False)
    p = staged.payload
    assert p["claim_commit"] == authority.claim_commit
    assert p["reservation_commit"] == authority.reservation_commit
    assert p["arm_commit"] == authority.arm_commit
    assert p["implementation_freeze_head"] == authority.permit.implementation_freeze_head
    assert p["prereg_freeze_head"] == lifecycle.PREREG_FREEZE_HEAD
    assert p["scientific_outcomes_inspected"] is True
    assert p["protected_2025_opened"] is False
    assert p["protected_2026_opened"] is False


# ==========================================================================
# 21. DATA AUTHORITY: no source-commit override.
# ==========================================================================


def test_reconstruction_has_no_source_commit_parameter():
    import inspect

    params = inspect.signature(recon.reconstruct_canonical_dataset).parameters
    assert "source_commit" not in params
    assert "data_commit" not in params
    assert "source_ref" not in params
    assert list(params)[0] == "permit"


@pytest.mark.parametrize(
    "kwargs",
    [{"source_commit": "a" * 40}, {"data_commit": "a" * 40},
     {"source_ref": "HEAD"}, {"dataset_commit": "a" * 40}, {"path": "/tmp"}],
)
def test_data_commit_override_is_refused(authority, kwargs):
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        recon.reconstruct_canonical_dataset(authority.permit, **kwargs)
    assert "DATA_SOURCE_OVERRIDE_FORBIDDEN" in str(exc.value)


def test_canonical_data_source_commit_is_the_frozen_prereg_freeze():
    assert recon.CANONICAL_DATA_SOURCE_COMMIT == "e2d543eadb5425473b6d4b8d24c177c1d7ae7930"
    assert recon.CANONICAL_DATA_SOURCE_COMMIT == lifecycle.PREREG_FREEZE_HEAD


def test_self_consistent_fake_dataset_commit_cannot_substitute(chain, authority, monkeypatch):
    """A descendant commit with a copied dataset_id/snapshot_id is unusable."""

    repo = chain["repo"]
    fake_dir = repo / recon.DATASET_DIR_REL
    fake_dir.mkdir(parents=True, exist_ok=True)
    fake_manifest = {
        "dataset_id": lifecycle.DATASET_ID,
        "snapshot_id": lifecycle.SNAPSHOT_ID,
        "durable_evidence_root_sha256": lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        "binance_objects": [], "okx_objects": [],
    }
    (repo / recon.DURABLE_MANIFEST_REL).write_text(json.dumps(fake_manifest))
    fake_commit = _commit(repo, "fake self-consistent dataset")

    # there is no parameter to point reconstruction at fake_commit at all
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        recon.reconstruct_canonical_dataset(authority.permit, source_commit=fake_commit)

    # and the hardcoded authority commit is not this fake one
    assert recon.CANONICAL_DATA_SOURCE_COMMIT != fake_commit


def test_protected_year_row_in_retained_source_fails_closed(monkeypatch):
    """Structural guard: no retained row may be at or after 2025-01-01."""

    from scripts.research.market_06_cross_venue_dislocation_authority import (
        Market06IncompleteExecution,
    )

    with pytest.raises(Market06IncompleteExecution) as exc:
        recon._reject_protected_year_row(
            recon.WINDOW_END_EXCLUSIVE_MS, leg="okx", logical_id="OKX_PAGE_1")
    assert "PROTECTED_YEAR_ROW_IN_RETAINED_SOURCE" in exc.value.reason
    # a pre-window row is legitimate and must NOT raise
    recon._reject_protected_year_row(
        recon.WINDOW_START_MS - recon.BAR_MS, leg="okx", logical_id="OKX_PAGE_1053")
