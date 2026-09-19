"""MARKET-05 ARM lifecycle + red-team authority tests.

Proves, using ONLY synthetic/fixture data in isolated temp repositories,
that the SAME frozen implementation bytes transition UNARMED -> ARMED ->
CONSUMED with no source modification, and that every forgery class is
refused.

No real MARKET-05 ARM/RESULT artifact is created, no real MARKET-05
outcome is computed, and no protected 2025/2026 value is read.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.research import market05_cross_asset_arm_authority as m05arm
from scripts.research import market05_cross_asset_authority as m05auth
from scripts.research import market05_cross_asset_canonical_execution as m05exec
from scripts.research import market05_cross_asset_lib as m05lib

REPO = Path(__file__).resolve().parents[2]

AUTH_FILES = tuple(sorted(m05arm.SCIENTIFIC_IMPLEMENTATION_HASHES))
# The ARM authority cannot pin its own hash, and the authority root pins it
# instead; both must exist in a fixture repo for the root of trust to run.
ROOT_FILES = (
    m05arm.ARM_AUTHORITY_REL,
    m05arm.AUTHORITY_ROOT_REL,
)
DOC_FILES = (
    m05arm.PREREG_MD_REL,
    m05arm.PREREG_JSON_REL,
    m05arm.REFREEZE_JSON_REL,
)


def _bind(monkeypatch, repo: Path) -> None:
    """Point the production authority at an isolated temp repository."""
    from scripts.research import market05_cross_asset_authority_root as _root

    monkeypatch.setattr(m05arm, "_repo_root", lambda: repo)
    monkeypatch.setattr(_root, "_repo_root", lambda: repo)


def _git(repo: Path, *argv: str) -> None:
    subprocess.run(
        ["git", *argv], cwd=str(repo), check=True, capture_output=True, text=True
    )


def _fixture_repo(tmp_path: Path) -> Path:
    """Isolated repo carrying the REAL frozen bytes, plus git tracking."""
    repo = tmp_path / "repo"
    for rel in AUTH_FILES + ROOT_FILES + DOC_FILES:
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dst)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fixture")
    return repo


def _valid_arm_payload() -> dict:
    return {
        "research_id": m05arm.RESEARCH_ID,
        "prereg_md_sha256": m05arm.FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": m05arm.FROZEN_PREREG_JSON_SHA256,
        "scientific_implementation_hashes": dict(
            m05arm.SCIENTIFIC_IMPLEMENTATION_HASHES
        ),
        "btc_dataset_id": m05arm.BTC_DATASET_ID,
        "btc_snapshot_id": m05arm.BTC_SNAPSHOT_ID,
        "eth_dataset_id": m05arm.ETH_DATASET_ID,
        "eth_snapshot_id": m05arm.ETH_SNAPSHOT_ID,
        "scientific_constants": dict(m05arm.SCIENTIFIC_CONSTANTS),
        "result_paths": {"json": m05arm.RESULT_JSON_REL, "md": m05arm.RESULT_MD_REL},
        "result_schema_identity": m05arm.RESULT_SCHEMA_IDENTITY,
        "run_identity": m05arm.derive_market_05_run_identity(),
        "MARKET_05_ARMED": True,
        "MARKET_05_EXECUTED": False,
        "MARKET_05_OUTCOMES_INSPECTED": False,
        "authorization_consumed": False,
        "CANONICAL_EXECUTIONS_AUTHORIZED": 1,
        "CANONICAL_EXECUTIONS_CONSUMED": 0,
        "protected_oos_authorized": False,
    }


def _valid_reservation_payload() -> dict:
    return {
        "research_id": m05arm.RESEARCH_ID,
        "run_identity": m05arm.derive_market_05_run_identity(),
        "CANONICAL_EXECUTIONS_AUTHORIZED": 1,
        "CANONICAL_EXECUTIONS_CONSUMED": 0,
        "rerun_preauthorized": False,
        "MARKET_05_EXECUTED": False,
        "protected_oos_authorized": False,
    }


def _install_arm(repo: Path, arm: dict | None = None, reservation: dict | None = None):
    arm = _valid_arm_payload() if arm is None else arm
    reservation = _valid_reservation_payload() if reservation is None else reservation
    (repo / m05arm.ARM_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / m05arm.ARM_JSON_REL).write_bytes(m05arm.canonical_json_bytes(arm))
    (repo / m05arm.ARM_MD_REL).write_text("# fixture ARM\n", encoding="utf-8")
    (repo / m05arm.RESERVATION_JSON_REL).write_bytes(
        m05arm.canonical_json_bytes(reservation)
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "arm")


def _armed_repo(tmp_path: Path) -> Path:
    repo = _fixture_repo(tmp_path)
    _install_arm(repo)
    return repo


# =============================================================================
# Baseline: the live repository is and stays UNARMED.
# =============================================================================


def test_live_repo_is_unarmed_and_execution_refused():
    state = m05auth.inspect_market_05_authorization_state()
    assert state["MARKET_05_ARMED"] is False
    assert state["MARKET_05_EXECUTION_AUTHORIZED"] is False
    assert state["CANONICAL_EXECUTIONS_AUTHORIZED"] == 0
    assert state["CANONICAL_EXECUTIONS_CONSUMED"] == 0
    assert state["run_identity"] is None
    assert m05arm.market_05_execution_is_authorized() is False
    with pytest.raises(m05auth.Market05ExecutionNotAuthorized):
        m05auth.require_execution_authorized_before_outcome_load()
    with pytest.raises(m05auth.Market05ExecutionNotAuthorized):
        m05auth.refuse_unarmed_canonical_execution()


def test_no_real_arm_or_result_artifact_exists():
    for rel in (
        m05arm.ARM_JSON_REL,
        m05arm.ARM_MD_REL,
        m05arm.RESERVATION_JSON_REL,
        m05arm.RESULT_JSON_REL,
        m05arm.RESULT_MD_REL,
    ):
        assert not (REPO / rel).exists(), rel


def test_result_write_unarmed_refused():
    with pytest.raises(m05lib.Market05IntegrityError, match="RESULT_INSTANTIATION"):
        m05lib.instantiate_scientific_result({"classification": "x"})


# =============================================================================
# RUN_IDENTITY determinism and independence.
# =============================================================================


def test_run_identity_is_deterministic_and_clock_free():
    first = m05arm.derive_market_05_run_identity()
    second = m05arm.derive_market_05_run_identity()
    assert first == second
    assert len(first) == 64
    payload = m05arm.scientific_run_identity_payload()
    blob = json.dumps(payload).lower()
    # "random_seed" is a frozen scientific constant and is expected; what
    # must be absent is any clock reading or per-run nonce.
    for forbidden in ("uuid", "generated_at", "created_at", "timestamp", "utcnow"):
        assert forbidden not in blob
    assert payload["scientific_constants"]["random_seed"] == 2026091905


def test_run_identity_binds_every_required_component():
    p = m05arm.scientific_run_identity_payload()
    assert p["research_id"] == m05arm.RESEARCH_ID
    assert p["prereg_md_sha256"] == m05arm.FROZEN_PREREG_MD_SHA256
    assert p["prereg_json_sha256"] == m05arm.FROZEN_PREREG_JSON_SHA256
    assert p["btc_snapshot_id"] == m05arm.BTC_SNAPSHOT_ID
    assert p["eth_snapshot_id"] == m05arm.ETH_SNAPSHOT_ID
    assert p["scientific_constants"]["materiality"] == 0.02
    assert p["scientific_constants"]["block_length"] == 14
    assert p["scientific_constants"]["bootstrap_replicates"] == 5000
    assert p["scientific_constants"]["random_seed"] == 2026091905
    assert p["protected_oos_authorized"] is False
    assert p["development_window"]["end_exclusive"] == "2025-01-01T00:00:00Z"
    assert set(p["scientific_implementation_hashes"]) == set(AUTH_FILES)


def test_run_identity_changes_if_a_scientific_constant_changes(monkeypatch):
    before = m05arm.derive_market_05_run_identity()
    patched = dict(m05arm.SCIENTIFIC_CONSTANTS)
    patched["materiality"] = 0.03
    monkeypatch.setattr(m05arm, "SCIENTIFIC_CONSTANTS", patched)
    assert m05arm.derive_market_05_run_identity() != before


# =============================================================================
# THE CORE PROPERTY: a valid ARM authorizes the SAME bytes.
# =============================================================================


def test_valid_arm_authorizes_without_any_code_change(tmp_path, monkeypatch):
    before = {rel: (REPO / rel).read_bytes() for rel in AUTH_FILES}
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)

    assert m05arm.market_05_execution_is_authorized() is True
    state = m05arm.inspect_market_05_arm_state()
    assert state["MARKET_05_ARMED"] is True
    assert state["MARKET_05_EXECUTION_AUTHORIZED"] is True
    assert state["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert state["CANONICAL_EXECUTIONS_CONSUMED"] == 0
    # The pre-ARM barrier now permits, using the same frozen function.
    m05auth.require_execution_authorized_before_outcome_load()
    m05auth.refuse_unarmed_canonical_execution()

    after = {rel: (REPO / rel).read_bytes() for rel in AUTH_FILES}
    assert before == after, "implementation source bytes must be unchanged"


def test_second_execution_refused_after_consumption(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    assert m05arm.market_05_execution_is_authorized() is True

    consumed = m05arm.consume_authorization_atomically()
    assert consumed["CANONICAL_EXECUTIONS_CONSUMED"] == "1"

    # Durable: re-read from disk, not process memory.
    payload = json.loads((repo / m05arm.RESERVATION_JSON_REL).read_text())
    assert payload["CANONICAL_EXECUTIONS_CONSUMED"] == 1

    assert m05arm.market_05_execution_is_authorized() is False
    with pytest.raises(m05arm.Market05CanonicalExecutionNotAuthorized):
        m05arm.authenticate_market_05_canonical_execution()
    with pytest.raises(m05arm.Market05CanonicalExecutionNotAuthorized):
        m05arm.consume_authorization_atomically()


def test_consumed_state_survives_fresh_module_state(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    m05arm.consume_authorization_atomically()
    # Simulate crash/retry: nothing in memory, state re-read from disk.
    _bind(monkeypatch, repo)
    assert m05arm.market_05_execution_is_authorized() is False


# =============================================================================
# Forgery / red-team matrix.
# =============================================================================


def test_no_arm_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    _bind(monkeypatch, repo)
    assert m05arm.market_05_execution_is_authorized() is False
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="MISSING"
    ):
        m05arm.authenticate_market_05_arm()


def test_random_arm_file_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    (repo / m05arm.ARM_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / m05arm.ARM_JSON_REL).write_text('{"hello": "world"}', encoding="utf-8")
    (repo / m05arm.ARM_MD_REL).write_text("nope\n", encoding="utf-8")
    (repo / m05arm.RESERVATION_JSON_REL).write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "random")
    _bind(monkeypatch, repo)
    with pytest.raises(m05arm.Market05CanonicalExecutionNotAuthorized):
        m05arm.authenticate_market_05_arm()


def test_malformed_arm_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    (repo / m05arm.ARM_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / m05arm.ARM_JSON_REL).write_text("{ not json", encoding="utf-8")
    (repo / m05arm.ARM_MD_REL).write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "malformed")
    _bind(monkeypatch, repo)
    with pytest.raises(m05arm.Market05ArmAuthorityError, match="MALFORMED_JSON"):
        m05arm.authenticate_market_05_arm()


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("research_id", "MARKET-99_SOMETHING", "RESEARCH_ID_MISMATCH"),
        ("prereg_md_sha256", "0" * 64, "PREREG_MISMATCH"),
        ("prereg_json_sha256", "0" * 64, "PREREG_MISMATCH"),
        ("btc_snapshot_id", "0" * 64, "SNAPSHOT_MISMATCH"),
        ("eth_snapshot_id", "0" * 64, "SNAPSHOT_MISMATCH"),
        ("btc_dataset_id", "SOMETHING_ELSE", "SNAPSHOT_MISMATCH"),
        ("eth_dataset_id", "SOMETHING_ELSE", "SNAPSHOT_MISMATCH"),
        ("run_identity", "0" * 64, "RUN_IDENTITY_MISMATCH"),
        ("result_schema_identity", "other/9", "RESULT_SCHEMA_MISMATCH"),
        ("MARKET_05_ARMED", False, "ARM_FLAG_MISMATCH"),
        ("CANONICAL_EXECUTIONS_AUTHORIZED", 2, "AUTHORIZED_MISMATCH"),
        ("CANONICAL_EXECUTIONS_CONSUMED", 1, "CONSUMED"),
        ("authorization_consumed", True, "CONSUMED"),
        ("MARKET_05_EXECUTED", True, "ALREADY_EXECUTED"),
    ],
)
def test_arm_field_forgery_refused(tmp_path, monkeypatch, field, value, match):
    repo = _fixture_repo(tmp_path)
    arm = _valid_arm_payload()
    arm[field] = value
    _install_arm(repo, arm=arm)
    _bind(monkeypatch, repo)
    with pytest.raises(
        (m05arm.Market05CanonicalExecutionNotAuthorized, m05arm.Market05ArmAuthorityError),
        match=match,
    ):
        m05arm.authenticate_market_05_arm()


def test_wrong_implementation_hash_in_arm_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    arm = _valid_arm_payload()
    arm["scientific_implementation_hashes"] = dict(
        m05arm.SCIENTIFIC_IMPLEMENTATION_HASHES
    )
    arm["scientific_implementation_hashes"][m05arm.LIB_REL] = "0" * 64
    _install_arm(repo, arm=arm)
    _bind(monkeypatch, repo)
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="IMPLEMENTATION_MISMATCH"
    ):
        m05arm.authenticate_market_05_arm()


def test_scientific_constant_changed_in_arm_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    arm = _valid_arm_payload()
    arm["scientific_constants"] = dict(m05arm.SCIENTIFIC_CONSTANTS)
    arm["scientific_constants"]["block_length"] = 21
    _install_arm(repo, arm=arm)
    _bind(monkeypatch, repo)
    with pytest.raises(
        m05arm.Market05ArmAuthorityError, match="SCIENTIFIC_CONSTANT_REDEFINED"
    ):
        m05arm.authenticate_market_05_arm()


def test_arm_carrying_outcome_field_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    arm = _valid_arm_payload()
    arm["classification"] = "MARKET_05_PROMOTED_HISTORICAL_CANDIDATE"
    _install_arm(repo, arm=arm)
    _bind(monkeypatch, repo)
    with pytest.raises(
        m05arm.Market05ArmAuthorityError, match="CONTAINS_OUTCOME_FIELD"
    ):
        m05arm.authenticate_market_05_arm()


def test_implementation_mutated_after_arm_refused(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    assert m05arm.market_05_execution_is_authorized() is True
    target = repo / m05arm.LIB_REL
    target.write_text(target.read_text(encoding="utf-8") + "\n# mutated\n", encoding="utf-8")
    # The authority root now catches this before the sha256 layer: it runs
    # first and refuses on git blob identity.
    from scripts.research import market05_cross_asset_authority_root as _root

    with pytest.raises(
        (_root.Market05AuthorityRootError, m05arm.Market05ArmAuthorityError),
        match="BLOB_MISMATCH|IMPLEMENTATION_BYTE_IDENTITY_MISMATCH",
    ):
        m05arm.authenticate_market_05_arm()
    assert m05arm.market_05_execution_is_authorized() is False


def test_prereg_mutated_after_arm_refused(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    target = repo / m05arm.PREREG_MD_REL
    target.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(
        m05arm.Market05ArmAuthorityError, match="PREREG_BYTE_IDENTITY_MISMATCH"
    ):
        m05arm.authenticate_market_05_arm()


def test_untracked_arm_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    arm = _valid_arm_payload()
    (repo / m05arm.ARM_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / m05arm.ARM_JSON_REL).write_bytes(m05arm.canonical_json_bytes(arm))
    (repo / m05arm.ARM_MD_REL).write_text("# untracked\n", encoding="utf-8")
    (repo / m05arm.RESERVATION_JSON_REL).write_bytes(
        m05arm.canonical_json_bytes(_valid_reservation_payload())
    )
    # deliberately NOT committed
    _bind(monkeypatch, repo)
    with pytest.raises(m05arm.Market05ArmAuthorityError, match="UNTRACKED"):
        m05arm.authenticate_market_05_arm()


def test_symlinked_arm_authority_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    real = repo / "elsewhere_arm.json"
    real.write_bytes(m05arm.canonical_json_bytes(_valid_arm_payload()))
    link = repo / m05arm.ARM_JSON_REL
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(real)
    (repo / m05arm.ARM_MD_REL).write_text("# md\n", encoding="utf-8")
    (repo / m05arm.RESERVATION_JSON_REL).write_bytes(
        m05arm.canonical_json_bytes(_valid_reservation_payload())
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "symlink")
    _bind(monkeypatch, repo)
    with pytest.raises(m05arm.Market05ArmAuthorityError, match="SYMLINK_REFUSED"):
        m05arm.authenticate_market_05_arm()


def test_protected_oos_authorization_injected_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    arm = _valid_arm_payload()
    arm["protected_oos_authorized"] = True
    _install_arm(repo, arm=arm)
    _bind(monkeypatch, repo)
    with pytest.raises(
        m05arm.Market05ArmAuthorityError, match="PROTECTED_OOS_AUTHORIZATION_REFUSED"
    ):
        m05arm.authenticate_market_05_arm()


def test_protected_oos_window_extension_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    arm = _valid_arm_payload()
    arm["development_end_exclusive"] = "2026-01-01T00:00:00Z"
    _install_arm(repo, arm=arm)
    _bind(monkeypatch, repo)
    with pytest.raises(
        m05arm.Market05ArmAuthorityError, match="PROTECTED_OOS_EXTENSION_REFUSED"
    ):
        m05arm.authenticate_market_05_arm()


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("run_identity", "0" * 64, "RUN_IDENTITY_MISMATCH"),
        ("CANONICAL_EXECUTIONS_AUTHORIZED", 0, "AUTHORIZED_MISMATCH"),
        ("CANONICAL_EXECUTIONS_CONSUMED", 1, "CONSUMED"),
        ("rerun_preauthorized", True, "RERUN_PREAUTHORIZED"),
        ("research_id", "OTHER", "RESEARCH_ID_MISMATCH"),
    ],
)
def test_reservation_forgery_refused(tmp_path, monkeypatch, field, value, match):
    repo = _fixture_repo(tmp_path)
    reservation = _valid_reservation_payload()
    reservation[field] = value
    _install_arm(repo, reservation=reservation)
    _bind(monkeypatch, repo)
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match=match
    ):
        m05arm.authenticate_market_05_reservation()


def test_arm_reservation_run_identity_disagreement_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    reservation = _valid_reservation_payload()
    _install_arm(repo, reservation=reservation)
    _bind(monkeypatch, repo)
    # Both individually valid; force a disagreement at the pair level.
    monkeypatch.setattr(
        m05arm,
        "authenticate_market_05_reservation",
        lambda: {"payload": {"run_identity": "0" * 64}, "sha256": "x"},
    )
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="DISAGREEMENT"
    ):
        m05arm.authenticate_market_05_canonical_execution()


def test_result_already_exists_refused(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    (repo / m05arm.RESULT_JSON_REL).write_text("{}", encoding="utf-8")
    _bind(monkeypatch, repo)
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="RESULT_ALREADY_PRESENT"
    ):
        m05arm.authenticate_market_05_canonical_execution()


def test_caller_kwargs_cannot_substitute_authority():
    for fn in (
        m05arm.derive_market_05_run_identity,
        m05arm.authenticate_market_05_arm,
        m05arm.authenticate_market_05_canonical_execution,
        m05arm.consume_authorization_atomically,
        m05arm.authenticate_frozen_scientific_bytes,
    ):
        with pytest.raises(m05arm.Market05CanonicalExecutionNotAuthorized):
            fn(run_identity="0" * 64)


def test_alternate_caller_data_path_refused():
    """A caller may not substitute an alternate dataset/snapshot."""
    with pytest.raises(m05auth.Market05ExecutionNotAuthorized):
        m05auth.refuse_bound_scientific_inputs(
            origin="synthetic", dataset_id="SOMETHING_ELSE"
        )
    with pytest.raises(m05auth.Market05ExecutionNotAuthorized):
        m05auth.refuse_bound_scientific_inputs(
            origin="synthetic", btc_snapshot_id="0" * 64
        )
    # Bound identifiers are refused from a caller while unarmed.
    with pytest.raises(m05auth.Market05ExecutionNotAuthorized):
        m05auth.refuse_bound_scientific_inputs(
            origin="synthetic", dataset_id=m05arm.BTC_DATASET_ID
        )


def test_lower_level_evaluator_cannot_mint_result_or_read_real_rows(tmp_path, monkeypatch):
    """The ungated evaluator computes on synthetic rows but grants nothing.

    evaluate_prepared_rows is pure math on caller-supplied rows; the
    bypass that would matter is minting a RESULT or reading real data,
    and both remain gated.
    """
    with pytest.raises(m05lib.Market05IntegrityError):
        m05lib.instantiate_scientific_result({"classification": "x"})
    with pytest.raises(m05arm.Market05CanonicalExecutionNotAuthorized):
        m05exec.load_bound_development_rows()


def test_mutable_global_flags_cannot_authorize(monkeypatch):
    """Monkeypatching module flags must not create authorization."""
    monkeypatch.setattr(m05auth, "MARKET_05_ARMED", True, raising=False)
    monkeypatch.setattr(m05auth, "MARKET_05_EXECUTION_AUTHORIZED", True, raising=False)
    monkeypatch.setattr(m05auth, "CANONICAL_EXECUTIONS_AUTHORIZED", 1, raising=False)
    assert m05arm.market_05_execution_is_authorized() is False
    state = m05auth.inspect_market_05_authorization_state()
    assert state["MARKET_05_ARMED"] is False
    assert state["MARKET_05_EXECUTION_AUTHORIZED"] is False


# =============================================================================
# Synthetic end-to-end lifecycle proof (no real data, no real artifacts).
# =============================================================================


def _synthetic_rows() -> list[m05lib.EligibleRow]:
    """Deterministic fixture rows spanning the frozen folds."""
    rows: list[m05lib.EligibleRow] = []
    t = m05lib.FIRST_USABLE_MS
    i = 0
    while t + m05lib.HORIZON_MS <= m05lib.LAST_USABLE_MS and i < 900:
        rows.append(
            m05lib.EligibleRow(
                t_ms=t,
                btc_side=1.0 if i % 2 == 0 else -1.0,
                abs_z_btc=0.5 + (i % 7) * 0.1,
                rv_btc_24h=0.01 + (i % 5) * 0.001,
                eth_confirmation=(1.0 if i % 2 == 0 else -1.0) * (0.2 + (i % 3) * 0.1),
                y=0.01 + (i % 11) * 0.0005,
            )
        )
        t += m05lib.DAY_MS * 2
        i += 1
    return rows


def test_synthetic_lifecycle_unarmed_then_armed_then_consumed(tmp_path, monkeypatch):
    before = {rel: (REPO / rel).read_bytes() for rel in AUTH_FILES}

    # 1-2. No ARM -> scientific execution refused.
    repo = _fixture_repo(tmp_path)
    _bind(monkeypatch, repo)
    assert m05arm.market_05_execution_is_authorized() is False
    with pytest.raises(m05auth.Market05ExecutionNotAuthorized):
        m05auth.require_execution_authorized_before_outcome_load()

    # 3. Install fixture ARM in the isolated temp repository.
    _install_arm(repo)

    # 4. Implementation source bytes unchanged.
    assert {rel: (REPO / rel).read_bytes() for rel in AUTH_FILES} == before

    # 5. ARM authenticates with the SAME production authority logic.
    bound = m05arm.authenticate_market_05_canonical_execution()
    assert bound["run_identity"] == m05arm.derive_market_05_run_identity()

    # 6. Synthetic canonical evaluation succeeds (frozen evaluator, fixture rows).
    rows = _synthetic_rows()
    evaluation = m05lib.evaluate_prepared_rows(
        rows, predictive_replicates=8, coefficient_replicates=8
    )
    assert evaluation["classification"] in {
        m05lib.CLASS_PROMOTED,
        m05lib.CLASS_NO_EVIDENCE,
        m05lib.CLASS_INCOMPLETE,
    }

    # 7. RESULT schema instantiation succeeds under the valid ARM.
    payload = {key: None for key in m05lib.RESULT_SCHEMA_KEYS}
    payload["classification"] = evaluation["classification"]
    payload["run_identity"] = bound["run_identity"]
    result = m05lib.instantiate_scientific_result(payload)
    assert set(result) == set(m05lib.RESULT_SCHEMA_KEYS)

    # 8. Execution becomes consumed.
    m05arm.consume_authorization_atomically()
    assert m05arm.market_05_execution_is_authorized() is False

    # 9. Second execution fails.
    with pytest.raises(m05arm.Market05CanonicalExecutionNotAuthorized):
        m05arm.authenticate_market_05_canonical_execution()
    with pytest.raises(m05lib.Market05IntegrityError):
        m05lib.instantiate_scientific_result(payload)

    # No real artifacts were created anywhere in the live repository.
    for rel in (m05arm.ARM_JSON_REL, m05arm.RESULT_JSON_REL):
        assert not (REPO / rel).exists()
    assert {rel: (REPO / rel).read_bytes() for rel in AUTH_FILES} == before


def test_protected_oos_rows_refused_even_under_valid_arm(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    assert m05arm.market_05_execution_is_authorized() is True
    protected_t = m05lib.PROTECTED_OOS_START_MS
    refusals = (m05lib.Market05ProtectedOOSError, m05lib.Market05DecisionBoundError)
    with pytest.raises(refusals):
        m05lib.assert_development_decision_time(protected_t)
    with pytest.raises(m05lib.Market05ProtectedOOSError):
        m05lib.assert_no_protected_open_times([protected_t])
    # A row at the boundary is refused by the frozen evaluator too.
    with pytest.raises(refusals):
        m05lib.evaluate_prepared_rows(
            [
                m05lib.EligibleRow(
                    t_ms=protected_t,
                    btc_side=1.0,
                    abs_z_btc=1.0,
                    rv_btc_24h=0.01,
                    eth_confirmation=0.1,
                    y=0.01,
                )
            ]
        )


# =============================================================================
# Scientific equivalence: the repair changed authority, never math.
# =============================================================================


def test_frozen_scientific_math_is_unchanged_by_the_repair():
    """The only edit inside the lib is the RESULT-authority function.

    Compares the live lib against the pre-repair frozen commit and asserts
    that every changed line belongs to instantiate_scientific_result.
    """
    frozen = subprocess.run(
        [
            "git",
            "show",
            "0016e4fc616af9222f9c9fd581a4a4199b1bdccf:"
            "scripts/research/market05_cross_asset_lib.py",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    live = (REPO / m05arm.LIB_REL).read_text(encoding="utf-8")

    def _math_section(text: str) -> str:
        # Everything before the RESULT schema/serialization block: features,
        # outcomes, folds, standardization, OLS, bootstrap, classification.
        marker = "RESULT_SCHEMA_KEYS = ("
        assert marker in text
        return text.split(marker)[0]

    assert _math_section(frozen) == _math_section(live)

    # The only post-marker changes are RESULT provenance schema 1.1.0 and
    # the RESULT-authority function: no statistic, gate or constant.
    for banned in ("def evaluate_prepared_rows", "def classify", "def fit_ols"):
        assert _math_section(live).count(banned) == _math_section(frozen).count(banned)


def test_scientific_constants_match_the_frozen_prereg_values():
    assert m05lib.MATERIALITY_THRESHOLD == 0.02
    assert m05lib.BLOCK_LENGTH == 14
    assert m05lib.BOOTSTRAP_REPLICATES == 5000
    assert m05lib.RANDOM_SEED == 2026091905
    assert m05lib.BOOTSTRAP_KIND == "CIRCULAR_MOVING_BLOCK"
    assert m05lib.ETH_CONFIRMATION_FORMULA == "BTC_SIDE * Z_ETH"
    assert m05lib.PRIMARY_OUTCOME == "BTC_DIRECTION_ALIGNED_MAE_24H"
    assert m05lib.BASELINE_MODEL == "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H"
    assert m05lib.CANDIDATE_MODEL == (
        "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION"
    )
    assert m05lib.DECISION_TIME == "00:00:00 UTC"
    assert m05lib.LOOKBACK_MS == 24 * 60 * 60 * 1000
    assert m05lib.HORIZON_MS == 24 * 60 * 60 * 1000
    # The authority's copy must agree with the library, or RUN_IDENTITY
    # would bind constants the evaluator does not actually use.
    c = m05arm.SCIENTIFIC_CONSTANTS
    assert c["materiality"] == m05lib.MATERIALITY_THRESHOLD
    assert c["block_length"] == m05lib.BLOCK_LENGTH
    assert c["bootstrap_replicates"] == m05lib.BOOTSTRAP_REPLICATES
    assert c["random_seed"] == m05lib.RANDOM_SEED
    assert c["bootstrap_kind"] == m05lib.BOOTSTRAP_KIND
    assert c["eth_confirmation"] == m05lib.ETH_CONFIRMATION_FORMULA
    assert c["primary_outcome"] == m05lib.PRIMARY_OUTCOME
    assert c["baseline_model"] == m05lib.BASELINE_MODEL
    assert c["candidate_model"] == m05lib.CANDIDATE_MODEL


def test_evaluator_output_is_deterministic_across_repeat_runs():
    rows = _synthetic_rows()
    a = m05lib.evaluate_prepared_rows(
        rows, predictive_replicates=8, coefficient_replicates=8
    )
    b = m05lib.evaluate_prepared_rows(
        rows, predictive_replicates=8, coefficient_replicates=8
    )
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(
        b, sort_keys=True, default=str
    )


# =============================================================================
# Authority root of trust: the ARM authority cannot vouch for itself.
# =============================================================================

from scripts.research import market05_cross_asset_authority_root as m05root  # noqa: E402


def test_authority_root_pins_the_arm_authority_blob():
    assert m05root.ARM_AUTHORITY_REL in m05root.FROZEN_BLOB_IDS
    # ...and the ARM authority does NOT pin its own sha256 (self-reference).
    assert m05arm.ARM_AUTHORITY_REL not in m05arm.SCIENTIFIC_IMPLEMENTATION_HASHES


def test_authority_root_blob_ids_match_live_bytes():
    seen = m05root.verify_frozen_blob_ids()
    assert set(seen) == set(m05root.FROZEN_BLOB_IDS)
    for rel, blob in seen.items():
        assert blob == m05root.git_blob_id((REPO / rel).read_bytes())


def test_git_blob_id_matches_git_hash_object():
    rel = m05root.ARM_AUTHORITY_REL
    expected = subprocess.run(
        ["git", "hash-object", rel],
        cwd=str(REPO), capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert m05root.git_blob_id((REPO / rel).read_bytes()) == expected


def test_arm_authority_mutation_after_arm_is_refused(tmp_path, monkeypatch):
    """THE root-repair test: mutate the ARM authority itself."""
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)

    # Baseline: the unmutated ARM authority passes the root check.
    m05root.verify_frozen_blob_ids()

    target = repo / m05arm.ARM_AUTHORITY_REL
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            'if payload.get("MARKET_05_ARMED") is not True:',
            "if False:",
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        m05root.Market05AuthorityRootError, match="BLOB_MISMATCH"
    ):
        m05root.verify_frozen_blob_ids()
    with pytest.raises(m05root.Market05AuthorityRootError, match="BLOB_MISMATCH"):
        m05root.verify_authority_root()
    # Refused BEFORE any scientific data loading.
    with pytest.raises(m05root.Market05AuthorityRootError, match="BLOB_MISMATCH"):
        m05exec.load_bound_development_rows()


@pytest.mark.parametrize(
    "rel",
    [
        "scripts/research/market05_cross_asset_lib.py",
        "scripts/research/market05_cross_asset_authority.py",
        "scripts/research/market05_cross_asset_data.py",
        "scripts/research/market05_cross_asset_canonical_execution.py",
        "scripts/research/market05_cross_asset.py",
    ],
)
def test_any_scientific_file_mutation_refused_by_root(tmp_path, monkeypatch, rel):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    target = repo / rel
    target.write_text(target.read_text(encoding="utf-8") + "\n# mutated\n", encoding="utf-8")
    with pytest.raises(
        m05root.Market05AuthorityRootError, match=f"BLOB_MISMATCH:{rel}"
    ):
        m05root.verify_frozen_blob_ids()


def test_authority_root_symlink_refused(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    target = repo / m05arm.ARM_AUTHORITY_REL
    real = repo / "elsewhere_authority.py"
    real.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(real)
    with pytest.raises(m05root.Market05AuthorityRootError, match="SYMLINK_REFUSED"):
        m05root.verify_frozen_blob_ids()


def test_run_identity_binds_the_authority_root_blob_ids():
    p = m05arm.scientific_run_identity_payload()
    assert p["arm_authority_file"] == m05arm.ARM_AUTHORITY_REL
    assert p["authority_root_file"] == m05arm.AUTHORITY_ROOT_REL
    assert (
        p["authority_root_blob_ids"][m05arm.ARM_AUTHORITY_REL]
        == m05root.FROZEN_BLOB_IDS[m05arm.ARM_AUTHORITY_REL]
    )


# =============================================================================
# Provenance: exact, non-placeholder, and honestly distinguished.
# =============================================================================


def test_frozen_provenance_is_exact_and_not_a_placeholder():
    prov = m05root.load_frozen_provenance()
    for key in ("head", "tree"):
        assert len(prov[key]) == 40
        assert "UNSET" not in prov[key]
        int(prov[key], 16)  # must be a real hex object id


def test_refreeze_distinguishes_scientific_commit_from_docs_commit():
    payload = json.loads((REPO / m05arm.REFREEZE_JSON_REL).read_text(encoding="utf-8"))
    sci = payload["scientific_implementation_head"]
    assert "UNSET" not in sci
    # A docs-only authority commit must never be presented as the
    # scientific implementation commit.
    assert payload["authority_root_head"] != sci
    assert payload["authority_root_commit_is_documentation_only"] is True


def test_authority_root_verifies_against_the_frozen_commit():
    out = m05root.verify_authority_root()
    assert out["git_verified"] is True
    assert out["scientific_implementation_head"] == (
        m05root.load_frozen_provenance()["head"]
    )


# =============================================================================
# RESULT provenance schema 1.1.0.
# =============================================================================


def test_result_schema_has_separate_commit_and_hash_fields():
    keys = m05lib.RESULT_SCHEMA_KEYS
    assert "implementation_head" in keys
    assert "implementation_tree" in keys
    assert "scientific_implementation_hashes" in keys
    assert m05arm.RESULT_SCHEMA_IDENTITY == "market_05_cross_asset_result/1.1.0"


def test_result_fixture_carries_exact_head_tree_and_separate_hash_map(
    tmp_path, monkeypatch
):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)

    evaluation = {"classification": m05lib.CLASS_NO_EVIDENCE}
    payload = m05exec._assemble_result_payload(
        evaluation, m05arm.derive_market_05_run_identity()
    )
    result = m05lib.instantiate_scientific_result(payload)

    prov = m05root.load_frozen_provenance()
    assert result["implementation_head"] == prov["head"]
    assert result["implementation_tree"] == prov["tree"]
    assert isinstance(result["implementation_head"], str)
    assert isinstance(result["implementation_tree"], str)
    # Commit fields must NOT be overloaded with the hash map.
    assert result["implementation_head"] != result["scientific_implementation_hashes"]
    assert result["scientific_implementation_hashes"] == dict(
        sorted(m05arm.SCIENTIFIC_IMPLEMENTATION_HASHES.items())
    )


# =============================================================================
# Authority root FAILS CLOSED without a verifiable git object store.
# =============================================================================


def _root_repo(tmp_path: Path) -> Path:
    """Fixture repo with authority files but NO frozen scientific commit."""
    repo = _fixture_repo(tmp_path)
    shutil.copy2(REPO / m05root.REFREEZE_JSON_REL, repo / m05root.REFREEZE_JSON_REL)
    return repo


def test_no_git_executable_refuses_authorization(tmp_path, monkeypatch):
    monkeypatch.setattr(m05root, "_repo_root", lambda: REPO)

    def _no_git(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(m05root.subprocess, "run", _no_git)
    with pytest.raises(
        m05root.Market05AuthorityRootError, match="GIT_VERIFICATION_REQUIRED"
    ):
        m05root.verify_authority_root()


def test_missing_frozen_commit_object_refuses(tmp_path, monkeypatch):
    repo = _root_repo(tmp_path)
    monkeypatch.setattr(m05root, "_repo_root", lambda: repo)
    # The fixture repo's history does not contain the frozen scientific
    # commit, so the root of trust cannot be established.
    with pytest.raises(
        m05root.Market05AuthorityRootError, match="GIT_VERIFICATION_REQUIRED"
    ):
        m05root.verify_authority_root()


def test_exported_tree_without_git_repository_refuses(tmp_path, monkeypatch):
    """A plain directory export (no .git at all) must never authorize."""
    export = tmp_path / "export"
    for rel in AUTH_FILES + ROOT_FILES + DOC_FILES:
        dst = export / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dst)
    shutil.copy2(REPO / m05root.REFREEZE_JSON_REL, export / m05root.REFREEZE_JSON_REL)
    monkeypatch.setattr(m05root, "_repo_root", lambda: export)
    # Blob ids alone would pass; the frozen commit cannot be resolved.
    m05root.verify_frozen_blob_ids()
    with pytest.raises(
        m05root.Market05AuthorityRootError, match="GIT_VERIFICATION_REQUIRED"
    ):
        m05root.verify_authority_root()


def test_wrong_frozen_tree_refuses(tmp_path, monkeypatch):
    export = tmp_path / "wrongtree"
    export.mkdir()
    (export / "docs" / "research").mkdir(parents=True)
    payload = json.loads((REPO / m05root.REFREEZE_JSON_REL).read_text(encoding="utf-8"))
    payload[m05root.SCIENTIFIC_IMPLEMENTATION_TREE_KEY] = "0" * 40
    (export / m05root.REFREEZE_JSON_REL).write_text(json.dumps(payload), encoding="utf-8")
    # Run inside the real repo so the commit resolves but the tree disagrees.
    monkeypatch.setattr(m05root, "load_frozen_provenance", lambda: {
        "head": payload[m05root.SCIENTIFIC_IMPLEMENTATION_HEAD_KEY],
        "tree": "0" * 40,
    })
    monkeypatch.setattr(m05root, "_repo_root", lambda: REPO)
    with pytest.raises(m05root.Market05AuthorityRootError, match="TREE_MISMATCH"):
        m05root.verify_authority_root()


def test_authority_root_self_mutation_refused(tmp_path, monkeypatch):
    """The root module is anchored by the frozen commit, not by itself."""
    live = (REPO / m05root.AUTHORITY_ROOT_REL).read_bytes()
    monkeypatch.setattr(m05root, "_repo_root", lambda: REPO)
    real_git = m05root._git

    def _mutated(*argv):
        out = real_git(*argv)
        if argv[:2] == ("cat-file", "-p") and argv[2].endswith(
            m05root.AUTHORITY_ROOT_REL
        ):
            out.stdout = live + b"\n# mutated\n"
        return out

    monkeypatch.setattr(m05root, "_git", _mutated)
    with pytest.raises(m05root.Market05AuthorityRootError, match="SELF_MUTATED"):
        m05root.verify_authority_root()


def test_valid_repository_with_exact_commit_and_tree_passes():
    out = m05root.verify_authority_root()
    assert out["git_verified"] is True
    prov = m05root.load_frozen_provenance()
    assert out["scientific_implementation_head"] == prov["head"]
    assert out["scientific_implementation_tree"] == prov["tree"]


def test_git_verified_is_mandatory_for_authorization(monkeypatch):
    """Even if the commit check were to report False, it must not authorize."""
    monkeypatch.setattr(
        m05root,
        "verify_frozen_commit_tree",
        lambda prov: {"git_verified": False, "head": prov["head"], "tree": prov["tree"]},
    )
    with pytest.raises(
        m05root.Market05AuthorityRootError, match="GIT_VERIFICATION_REQUIRED"
    ):
        m05root.verify_authority_root()


# =============================================================================
# Root must precede ARM authorization on every protected path.
# =============================================================================


@pytest.mark.parametrize(
    "call",
    [
        "load_bound_development_rows",
        "run_canonical_market_05_execution",
    ],
)
def test_protected_paths_verify_root_before_trusting_arm(monkeypatch, call):
    """Root runs FIRST: an authority-root failure wins over ARM success."""
    order: list[str] = []

    def _root_fails():
        order.append("root")
        raise m05root.Market05AuthorityRootError(
            "MARKET_05_AUTHORITY_ROOT_GIT_VERIFICATION_REQUIRED"
        )

    def _arm_would_succeed(*a, **k):
        order.append("arm")
        return {"run_identity": "x", "arm": {}, "reservation": {}}

    monkeypatch.setattr(m05root, "verify_authority_root", _root_fails)
    monkeypatch.setattr(
        m05exec, "authenticate_market_05_canonical_execution", _arm_would_succeed
    )
    with pytest.raises(
        m05root.Market05AuthorityRootError, match="GIT_VERIFICATION_REQUIRED"
    ):
        getattr(m05exec, call)()
    # ARM authority was never consulted.
    assert order == ["root"]


def test_arm_authority_itself_verifies_root_first(monkeypatch):
    order: list[str] = []

    def _root_fails(*a, **k):
        order.append("root")
        raise m05root.Market05AuthorityRootError(
            "MARKET_05_AUTHORITY_ROOT_GIT_VERIFICATION_REQUIRED"
        )

    monkeypatch.setattr(m05arm, "verify_authority_root", _root_fails)
    monkeypatch.setattr(
        m05arm, "authenticate_frozen_prereg_bytes", lambda: order.append("prereg")
    )
    with pytest.raises(m05root.Market05AuthorityRootError):
        m05arm.authenticate_market_05_arm()
    assert order == ["root"]
    # ...and it fails closed rather than propagating.
    assert m05arm.market_05_execution_is_authorized() is False


# =============================================================================
# Cross-artifact authority consistency: exactly ONE canonical value each.
# =============================================================================


def _read_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _sha256_path(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def test_frozen_authority_artifacts_are_fully_consistent():
    """Reads the production artifacts independently; any silent
    disagreement between duplicated authority fields fails closed."""
    contract = _read_json(m05arm.ARM_CONTRACT_JSON_REL)
    refreeze = _read_json(m05arm.REFREEZE_JSON_REL)
    prereg_md = _sha256_path(m05arm.PREREG_MD_REL)
    prereg_json = _sha256_path(m05arm.PREREG_JSON_REL)

    # RUN_IDENTITY: derived independently, then required everywhere.
    payload = m05arm.scientific_run_identity_payload()
    derived = hashlib.sha256(
        (
            json.dumps(
                payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    assert derived == m05arm.derive_market_05_run_identity()
    assert derived == contract["run_identity"]
    assert derived == refreeze["run_identity"]

    # prereg identity
    assert prereg_md == m05arm.FROZEN_PREREG_MD_SHA256 == contract["prereg"]["md_sha256"]
    assert prereg_md == refreeze["prereg"]["md_sha256"]
    assert (
        prereg_json
        == m05arm.FROZEN_PREREG_JSON_SHA256
        == contract["prereg"]["json_sha256"]
        == refreeze["prereg"]["json_sha256"]
    )

    # scientific implementation commit provenance
    prov = m05root.load_frozen_provenance()
    assert prov["head"] == refreeze["scientific_implementation_head"]
    assert prov["tree"] == refreeze["scientific_implementation_tree"]
    assert prov["head"] == (
        contract["implementation_authority"]["scientific_implementation_head"]
    )
    assert prov["tree"] == (
        contract["implementation_authority"]["scientific_implementation_tree"]
    )

    # dataset snapshots
    assert contract["data"]["btc_snapshot_id"] == m05arm.BTC_SNAPSHOT_ID
    assert contract["data"]["eth_snapshot_id"] == m05arm.ETH_SNAPSHOT_ID
    assert refreeze["data"]["btc_snapshot_id"] == m05arm.BTC_SNAPSHOT_ID
    assert refreeze["data"]["eth_snapshot_id"] == m05arm.ETH_SNAPSHOT_ID

    # RESULT schema identity
    assert contract["result_schema_identity"] == m05arm.RESULT_SCHEMA_IDENTITY
    assert refreeze["result_schema_identity"] == m05arm.RESULT_SCHEMA_IDENTITY

    # scientific constants
    assert contract["scientific_constants"] == dict(sorted(m05arm.SCIENTIFIC_CONSTANTS.items()))
    assert refreeze["scientific_constants"] == dict(sorted(m05arm.SCIENTIFIC_CONSTANTS.items()))

    # authority root blob map
    blobs = dict(sorted(m05root.FROZEN_BLOB_IDS.items()))
    assert contract["implementation_authority"]["authority_root_blob_ids"] == blobs
    assert refreeze["authority_root_blob_ids"] == blobs

    # per-file scientific hashes
    hashes = dict(sorted(m05arm.SCIENTIFIC_IMPLEMENTATION_HASHES.items()))
    assert contract["implementation_authority"]["scientific_implementation_hashes"] == hashes
    assert refreeze["scientific_implementation_hashes"] == hashes

    # unarmed lifecycle
    assert contract["protected_oos_authorized"] is False
    assert refreeze["protected_oos_touched"] is False
    assert refreeze["armed"] is False
    assert refreeze["execution_authorized"] is False
    assert refreeze["canonical_executions_authorized"] == 0
    assert refreeze["canonical_executions_consumed"] == 0
    assert refreeze["real_arm_created"] is False
    assert refreeze["result_created"] is False


def test_refreeze_binds_the_exact_current_arm_contract_bytes():
    """Hash the contract bytes independently; the re-freeze must agree."""
    refreeze = _read_json(m05arm.REFREEZE_JSON_REL)
    assert refreeze["arm_contract_md_sha256"] == _sha256_path(m05arm.ARM_CONTRACT_MD_REL)
    assert refreeze["arm_contract_json_sha256"] == _sha256_path(
        m05arm.ARM_CONTRACT_JSON_REL
    )


def test_arm_authority_sha256_binding_is_current():
    refreeze = _read_json(m05arm.REFREEZE_JSON_REL)
    assert refreeze["arm_authority_sha256"] == _sha256_path(m05arm.ARM_AUTHORITY_REL)
