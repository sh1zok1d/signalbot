"""One-shot execution lifecycle tests (red-team F-05 / F-07 / F-08).

Proves the central repaired property: a FUTURE tracked ARM can authorize
the EXACT frozen implementation bytes with no edit to any scientific
module. Uses synthetic Git fixtures; creates no live ARM, reservation, or
RESULT in this repository, and runs no canonical execution.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.research import market_06_execution_lifecycle as lifecycle
from scripts.research import market_06_git_authority as gitauth
from scripts.research.market_06_git_authority import Market06GitAuthorityError

REPO = Path(__file__).resolve().parents[2]
FREEZE_REL = "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.json"


def _run(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=test",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().strip()


def _freeze_payload(impl_head: str, impl_tree: str, module_sha: dict[str, str]) -> dict:
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


def _arm_payload(freeze_head: str, freeze_tree: str, run_identity: str) -> dict:
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


@pytest.fixture
def armed(tmp_path, monkeypatch):
    """A synthetic repo carrying the real frozen module bytes + a valid ARM."""

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q", "-b", "main")
    for rel in lifecycle.SCIENTIFIC_MODULE_RELPATHS:
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dst)
    (repo / "docs/research").mkdir(parents=True, exist_ok=True)
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "implementation")
    impl_head = _run(repo, "rev-parse", "HEAD")
    impl_tree = _run(repo, "rev-parse", "HEAD^{tree}")

    monkeypatch.setattr(gitauth, "repo_root", lambda: repo)
    module_sha = lifecycle.live_module_sha256()
    run_identity = lifecycle.derive_run_identity(module_sha)

    (repo / FREEZE_REL).write_text(
        json.dumps(_freeze_payload(impl_head, impl_tree, module_sha), indent=2)
    )
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "freeze")
    freeze_head = _run(repo, "rev-parse", "HEAD")
    freeze_tree = _run(repo, "rev-parse", "HEAD^{tree}")

    (repo / lifecycle.ARM_JSON_REL).write_text(
        json.dumps(_arm_payload(freeze_head, freeze_tree, run_identity), indent=2)
    )
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "arm")
    arm_commit = _run(repo, "rev-parse", "HEAD")

    return {
        "repo": repo,
        "impl_head": impl_head,
        "freeze_head": freeze_head,
        "freeze_tree": freeze_tree,
        "arm_commit": arm_commit,
        "run_identity": run_identity,
        "module_sha": module_sha,
    }


def _rewrite_arm(armed, mutate) -> str:
    repo = armed["repo"]
    payload = json.loads((repo / lifecycle.ARM_JSON_REL).read_text())
    mutate(payload)
    (repo / lifecycle.ARM_JSON_REL).write_text(json.dumps(payload, indent=2))
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "arm-mutated")
    return _run(repo, "rev-parse", "HEAD")


# --------------------------------------------------------------------------
# No ARM in the live repository: canonical execution must refuse today.
# --------------------------------------------------------------------------


def test_live_repository_is_in_terminal_consumed_state():
    """MARKET-06 reached its terminal RESULT; the shot is spent.

    The pre-execution assertions (no ARM, no RESULT, unauthorized because
    no claim) are historically false BY DESIGN after the one canonical run.
    What must still hold is that the chain is fully tracked and that a
    further canonical execution refuses as already consumed.
    """

    state = lifecycle.inspect_lifecycle_state()
    assert state["arm_exists"] is True
    assert state["reservation_exists"] is True
    assert state["claim_exists"] is True
    assert state["result_exists"] is True
    assert state["execution_authorized"] is False
    assert state["authority_chain"] == (
        "CLAIM -> RESERVATION -> ARM -> IMPLEMENTATION_FREEZE"
    )
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.canonical_execution_permit_or_refuse()
    assert "ALREADY_CONSUMED" in str(exc.value)


def test_terminal_result_binds_the_exact_authority_chain():
    result = json.loads(
        (REPO / lifecycle.RESULT_JSON_REL).read_text(encoding="utf-8")
    )
    assert result["run_identity"] == "f3aa51372594d710a8f705d761d857f8385d0b848fb0ed59a36b27a16ce25c22"
    assert result["claim_commit"] == "6d2814491a99bcd4e7ef4fcdd1c6ee0bc3443657"
    assert result["reservation_commit"] == "de478963823817a705ced22efa23d883f2f2e56e"
    assert result["arm_commit"] == "2d5815760241042e812eef5e70357a693f38e1c6"
    assert result["implementation_freeze_head"] == "a83225241a48baf7620731f0a791ed93f0392343"
    assert result["classification"] == "MARKET_06_NO_EVIDENCE"
    assert result["protected_2025_opened"] is False
    assert result["protected_2026_opened"] is False


def test_sealed_result_bytes_are_unchanged():
    import hashlib

    raw = (REPO / lifecycle.RESULT_JSON_REL).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "67f6f14c9221d3d0be2c130938f6ff8588aadc6eabc52126dd00a5fbbedd2a53"
    )


CANONICAL_RUN_IDENTITY = (
    "f3aa51372594d710a8f705d761d857f8385d0b848fb0ed59a36b27a16ce25c22"
)


def test_second_shot_is_refused_by_the_local_attempt_ledger(tmp_path, monkeypatch):
    """A ledger recording the run identity refuses a second shot.

    Hermetic by construction: this uses a SYNTHETIC ledger under tmp_path
    and never reads, writes, or depends on the real canonical attempt
    ledger, which is gitignored and exists only in the designated canonical
    checkout (so it is absent in a fresh clone or CI).
    """

    ledger = tmp_path / "attempts.json"
    ledger.write_text(
        json.dumps(
            {
                CANONICAL_RUN_IDENTITY: {
                    "claim_commit": "6d2814491a99bcd4e7ef4fcdd1c6ee0bc3443657",
                    "reservation_commit": "de478963823817a705ced22efa23d883f2f2e56e",
                    "arm_commit": "2d5815760241042e812eef5e70357a693f38e1c6",
                    "claim_state": lifecycle.CLAIM_STATE_CLAIMED,
                    "scientific_outcomes_inspected": False,
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle, "_attempt_ledger_path", lambda: ledger)

    assert lifecycle.read_attempt_ledger()[CANONICAL_RUN_IDENTITY]["claim_state"] == (
        lifecycle.CLAIM_STATE_CLAIMED
    )
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.assert_shot_not_already_consumed(CANONICAL_RUN_IDENTITY)
    assert "ALREADY_CLAIMED" in str(exc.value)


def test_empty_synthetic_ledger_does_not_claim_local_consumption(tmp_path, monkeypatch):
    """The complementary direction: an empty ledger must NOT refuse."""

    monkeypatch.setattr(lifecycle, "_attempt_ledger_path", lambda: tmp_path / "absent.json")
    assert lifecycle.read_attempt_ledger() == {}
    lifecycle.assert_shot_not_already_consumed(CANONICAL_RUN_IDENTITY)

    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(lifecycle, "_attempt_ledger_path", lambda: empty)
    assert lifecycle.read_attempt_ledger() == {}
    lifecycle.assert_shot_not_already_consumed(CANONICAL_RUN_IDENTITY)

    # a ledger holding a DIFFERENT run identity must not refuse this one
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"0" * 64: {"claim_state": "X"}}), encoding="utf-8")
    monkeypatch.setattr(lifecycle, "_attempt_ledger_path", lambda: other)
    lifecycle.assert_shot_not_already_consumed(CANONICAL_RUN_IDENTITY)


def test_ledger_tests_never_touch_the_real_canonical_ledger():
    """Guard: the real ledger is gitignored and must stay untracked."""

    real = REPO / lifecycle.EXECUTION_ATTEMPT_LEDGER_REL
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", lifecycle.EXECUTION_ATTEMPT_LEDGER_REL],
        cwd=REPO,
        capture_output=True,
    )
    assert proc.returncode != 0, "the canonical attempt ledger must never be tracked"
    assert lifecycle.EXECUTION_ATTEMPT_LEDGER_REL in (REPO / ".gitignore").read_text()
    # this suite must not depend on whether the real ledger happens to exist
    assert real.name not in ("", None)


def test_permit_cannot_be_forged():
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        lifecycle.ExecutionPermit(
            run_identity="x",
            arm_commit="y",
            implementation_freeze_head="z",
            implementation_freeze_tree="w",
            dataset_id=lifecycle.DATASET_ID,
            snapshot_id=lifecycle.SNAPSHOT_ID,
            durable_evidence_root_sha256=lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
            authorization_kind=lifecycle.AUTHORIZATION_KIND,
        )
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        lifecycle.require_permit({"authorized": True})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"authorize": True},
        {"force": True},
        {"execution_authorized": True},
        {"run_identity": "x"},
        {"snapshot_id": "x"},
        {"expected_sha256": "x"},
        {"path": "/tmp/x"},
    ],
)
def test_caller_kwargs_cannot_authorize(kwargs):
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        lifecycle.verify_execution_arm(**kwargs)


@pytest.mark.parametrize("key", lifecycle.BYPASS_ENV_KEYS)
def test_environment_variables_cannot_authorize(monkeypatch, key):
    monkeypatch.setenv(key, "1")
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        lifecycle.verify_execution_arm()


# --------------------------------------------------------------------------
# A valid future ARM authorizes the SAME frozen bytes.
# --------------------------------------------------------------------------


def test_valid_arm_authorizes_the_same_frozen_implementation(armed):
    permit = lifecycle.verify_execution_arm(arm_commit=armed["arm_commit"])
    assert permit.run_identity == armed["run_identity"]
    assert permit.implementation_freeze_head == armed["freeze_head"]
    assert permit.authorization_kind == lifecycle.AUTHORIZATION_KIND
    assert lifecycle.require_permit(permit) is permit
    # the bytes authorized are byte-identical to the live repository modules
    for rel, digest in armed["module_sha"].items():
        assert digest == lifecycle.live_module_sha256()[rel]


def test_run_identity_is_content_only_and_deterministic(armed):
    first = lifecycle.derive_run_identity(armed["module_sha"])
    second = lifecycle.derive_run_identity(armed["module_sha"])
    assert first == second == armed["run_identity"]
    preimage = lifecycle.run_identity_preimage(armed["module_sha"])
    blob = json.dumps(preimage).lower()
    for forbidden in ("uuid", "generated_at", "created_at", "utcnow", "commit_head"):
        assert forbidden not in blob


def test_mutated_scientific_module_invalidates_the_arm(armed):
    target = armed["repo"] / "scripts/research/market_06_cross_venue_dislocation_evaluator.py"
    target.write_text(target.read_text() + "\n# post-ARM mutation\n")
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.verify_execution_arm(arm_commit=armed["arm_commit"])
    assert "LIVE_MODULE_BYTES_DIFFER_FROM_FREEZE" in str(exc.value)


def test_scientific_drift_between_freeze_and_arm_is_refused(armed):
    repo = armed["repo"]
    target = repo / "scripts/research/market_06_cross_venue_dislocation_bootstrap.py"
    target.write_text(target.read_text() + "\n# drift\n")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "drift")
    drifted = _run(repo, "rev-parse", "HEAD")
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        lifecycle.verify_execution_arm(arm_commit=drifted)


@pytest.mark.parametrize(
    "field,value",
    [
        ("research_id", "MARKET-99"),
        ("dataset_id", "WRONG"),
        ("snapshot_id", "0" * 64),
        ("durable_evidence_root_sha256", "0" * 64),
        ("prereg_freeze_head", "0" * 40),
        ("authorization_kind", "ROLLING"),
        ("scientific_outcomes_inspected_before_arm", True),
        ("protected_2025_opened", True),
        ("protected_2026_opened", True),
        ("one_shot", False),
        ("run_identity", "0" * 64),
    ],
)
def test_malformed_or_fake_arm_is_rejected(armed, field, value):
    commit = _rewrite_arm(armed, lambda p: p.__setitem__(field, value))
    with pytest.raises(
        (lifecycle.Market06ExecutionNotAuthorized, lifecycle.Market06LifecycleError)
    ):
        lifecycle.verify_execution_arm(arm_commit=commit)


def test_missing_required_arm_field_is_rejected(armed):
    commit = _rewrite_arm(armed, lambda p: p.pop("run_identity"))
    with pytest.raises(lifecycle.Market06LifecycleError):
        lifecycle.verify_execution_arm(arm_commit=commit)


def test_untracked_working_tree_arm_does_not_authorize(armed, monkeypatch):
    """An ARM file that exists on disk but in no commit authorizes nothing."""

    repo = armed["repo"]
    _run(repo, "checkout", "-q", armed["impl_head"])
    (repo / lifecycle.ARM_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / lifecycle.ARM_JSON_REL).write_text(
        json.dumps(_arm_payload(armed["freeze_head"], armed["freeze_tree"], armed["run_identity"]))
    )
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.verify_execution_arm(arm_commit=armed["impl_head"])
    assert "NO_TRACKED_ARM" in str(exc.value)


def test_arm_must_descend_from_its_implementation_freeze(armed):
    with pytest.raises(
        (lifecycle.Market06ExecutionNotAuthorized, Market06GitAuthorityError)
    ):
        lifecycle.verify_execution_arm(arm_commit=armed["impl_head"])


# --------------------------------------------------------------------------
# Reservation / result state machine + one-shot refusal.
# --------------------------------------------------------------------------


def test_reservation_is_required_before_science(armed):
    """The ARM commit itself carries no reservation (chain: A -> R)."""

    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.verify_execution_reservation_from_commit(armed["arm_commit"])
    assert "NO_TRACKED_RESERVATION" in str(exc.value)


def _reservation(armed, **overrides) -> dict:
    payload = {
        "research_id": lifecycle.RESEARCH_ID,
        "run_identity": armed["run_identity"],
        "arm_commit": armed["arm_commit"],
        "implementation_freeze_head": armed["freeze_head"],
        "implementation_freeze_tree": armed["freeze_tree"],
        "dataset_id": lifecycle.DATASET_ID,
        "snapshot_id": lifecycle.SNAPSHOT_ID,
        "durable_evidence_root_sha256": lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        "authorization_kind": lifecycle.AUTHORIZATION_KIND,
        "consumed": False,
        "result_target_paths": [lifecycle.RESULT_JSON_REL, lifecycle.RESULT_MD_REL],
        "claim_target_path": lifecycle.CLAIM_JSON_REL,
        "scientific_outcomes_inspected_before_reservation": False,
        "protected_2025_opened": False,
        "protected_2026_opened": False,
    }
    payload.update(overrides)
    return payload


def _commit_reservation(armed, payload) -> str:
    repo = armed["repo"]
    (repo / lifecycle.RESERVATION_JSON_REL).write_text(json.dumps(payload, indent=2))
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "reservation")
    return _run(repo, "rev-parse", "HEAD")


def test_valid_unconsumed_reservation_is_accepted(armed):
    commit = _commit_reservation(armed, _reservation(armed))
    permit, reservation, resolved = lifecycle.verify_execution_reservation_from_commit(
        commit
    )
    assert resolved == commit
    assert reservation["consumed"] is False
    assert reservation["run_identity"] == permit.run_identity
    assert permit.arm_commit == armed["arm_commit"]


def test_consumed_reservation_is_refused(armed):
    commit = _commit_reservation(armed, _reservation(armed, consumed=True))
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.verify_execution_reservation_from_commit(commit)
    assert "RESERVATION_ALREADY_CONSUMED" in str(exc.value)


def test_reservation_bound_to_a_different_run_identity_is_refused(armed):
    commit = _commit_reservation(armed, _reservation(armed, run_identity="0" * 64))
    with pytest.raises(lifecycle.Market06LifecycleError):
        lifecycle.verify_execution_reservation_from_commit(commit)


def test_second_canonical_run_is_refused_once_a_result_exists(armed):
    repo = armed["repo"]
    permit = lifecycle.verify_execution_arm(arm_commit=armed["arm_commit"])
    (repo / lifecycle.RESULT_JSON_REL).write_text(
        json.dumps({"run_identity": permit.run_identity, "classification": "REDACTED"})
    )
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "result")
    consumed = _run(repo, "rev-parse", "HEAD")
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
        lifecycle.verify_execution_arm(arm_commit=consumed)
    assert "ALREADY_CONSUMED" in str(exc.value)


def test_execution_lock_is_atomic_and_scoped(armed, monkeypatch):
    permit = lifecycle.verify_execution_arm(arm_commit=armed["arm_commit"])
    with lifecycle.Market06ExecutionLock(permit.run_identity) as lock:
        assert lock.path.exists()
        with pytest.raises(lifecycle.Market06ExecutionNotAuthorized) as exc:
            with lifecycle.Market06ExecutionLock(permit.run_identity):
                pass
        assert "LOCK_HELD" in str(exc.value)
    assert not lock.path.exists()
    assert "not a distributed mutex" in lifecycle.Market06ExecutionLock.__doc__.lower()


# --------------------------------------------------------------------------
# Hardened Git object access.
# --------------------------------------------------------------------------


def test_rev_parse_echo_is_not_accepted_as_existence():
    ghost = "0" * 39 + "1"
    proc = gitauth.git("rev-parse", ghost)
    assert proc.stdout.decode().strip() == ghost  # git echoes it back
    with pytest.raises(Market06GitAuthorityError):
        gitauth.require_commit(ghost)


def test_git_environment_redirection_is_neutralized(monkeypatch, tmp_path):
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    _run(decoy, "init", "-q", "-b", "main")
    for var in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
    ):
        monkeypatch.setenv(var, str(decoy))
    env = gitauth._git_env()
    for var in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
    ):
        assert var not in env
    # the real prereg freeze is still resolvable despite the redirection attempt
    assert gitauth.require_commit(lifecycle.PREREG_FREEZE_HEAD)


def test_replace_refs_are_disabled():
    proc = gitauth.git("rev-parse", "HEAD")
    assert proc.returncode == 0
    exe_argv = ["--no-replace-objects", "core.useReplaceRefs=false"]
    source = Path(gitauth.__file__).read_text()
    for token in exe_argv:
        assert token in source
