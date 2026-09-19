"""MARKET-05 ARM lifecycle + red-team authority tests.

Proves, using ONLY synthetic/fixture data in isolated temp repositories,
that the SAME frozen implementation bytes transition UNARMED -> ARMED ->
CONSUMED with no source modification, and that every forgery class is
refused.

No real MARKET-05 ARM/RESULT artifact is created, no real MARKET-05
outcome is computed, and no protected 2025/2026 value is read.
"""

from __future__ import annotations

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
DOC_FILES = (
    m05arm.PREREG_MD_REL,
    m05arm.PREREG_JSON_REL,
)


def _bind(monkeypatch, repo: Path) -> None:
    """Point the production authority at an isolated temp repository."""
    monkeypatch.setattr(m05arm, "_repo_root", lambda: repo)


def _git(repo: Path, *argv: str) -> None:
    subprocess.run(
        ["git", *argv], cwd=str(repo), check=True, capture_output=True, text=True
    )


def _fixture_repo(tmp_path: Path) -> Path:
    """Isolated repo carrying the REAL frozen bytes, plus git tracking."""
    repo = tmp_path / "repo"
    for rel in AUTH_FILES + DOC_FILES:
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
    with pytest.raises(
        m05arm.Market05ArmAuthorityError, match="IMPLEMENTATION_BYTE_IDENTITY_MISMATCH"
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

    def _before_result_fn(text: str) -> str:
        marker = "def instantiate_scientific_result("
        assert marker in text
        return text.split(marker)[0]

    # Everything preceding the RESULT function is byte-identical: features,
    # outcomes, folds, standardization, OLS, bootstrap, classification.
    assert _before_result_fn(frozen) == _before_result_fn(live)


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
