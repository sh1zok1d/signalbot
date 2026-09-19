"""MARKET-03 ARM fail-closed tests. Synthetic / stubbed payloads only.

Does not load bound MARKET-03 spot or funding rows into strategy logic
or rerun the canonical scientific path. Live reservation is consumed.
Unused ARM fixtures are restored from the unused ARM commit.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.research import market_03_public_strategy_arm_authority as m03arm
from scripts.research.market_03_public_strategy_arm_authority import (
    ARM_JSON_SHA256,
    ARM_MD_SHA256,
    ARM_OUTCOME_FIELDS,
    B2_06_SNAPSHOT_ID,
    CANONICAL_EXECUTIONS_AUTHORIZED,
    CANONICAL_EXECUTIONS_CONSUMED,
    FROZEN_IMPLEMENTATION_HEAD,
    FROZEN_IMPLEMENTATION_TREE,
    FROZEN_MARKET_03_RUN_IDENTITY,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    FUNDING_SNAPSHOT_ID,
    IMPL_FREEZE_JSON_SHA256,
    IMPL_FREEZE_MD_SHA256,
    LIB_SHA256,
    AUTHORITY_SHA256,
    EXECUTE_SHA256,
    Market03ArmAuthorityError,
    Market03CanonicalExecutionNotAuthorized,
    RESERVATION_JSON_SHA256,
    SPOT_SNAPSHOT_ID,
    authenticate_frozen_prereg_bytes,
    authenticate_frozen_scientific_bytes,
    authenticate_market_03_arm,
    authenticate_market_03_canonical_execution,
    authenticate_market_03_implementation_freeze,
    authenticate_market_03_reservation,
    consume_authorization_atomically,
    derive_market_03_run_identity,
    inspect_market_03_arm_state,
    reject_protected_oos_extension,
)
from scripts.research.market_03_public_strategy_authority import (
    inspect_market_03_authorization_state,
)
from scripts.research.market_03_public_strategy_canonical_execution import (
    Market03CanonicalExecutionReserved,
    PreConsumptionBlocker,
    authenticate_pre_execution,
    evaluate_bound_after_arm_consumption,
    permit_canonical_scientific_execution,
    run_canonical_market_03,
)
from scripts.research.market_03_public_strategy_execute import (
    execute_bound_market_03,
)


REPO = Path(__file__).resolve().parents[2]
UNUSED_ARM_HEAD = "e3c5de3bcb68173af0bfb08a8c42f4a5e8981c5a"
_UNUSED_ARM_RELS = {
    m03arm.ARM_MD_REL,
    m03arm.ARM_JSON_REL,
    m03arm.RESERVATION_JSON_REL,
}
_TRACKED = (
    m03arm.PREREG_MD_REL,
    m03arm.PREREG_JSON_REL,
    m03arm.IMPL_FREEZE_MD_REL,
    m03arm.IMPL_FREEZE_JSON_REL,
    m03arm.ARM_MD_REL,
    m03arm.ARM_JSON_REL,
    m03arm.RESERVATION_JSON_REL,
    m03arm.LIB_REL,
    m03arm.AUTHORITY_REL,
    m03arm.EXECUTE_REL,
    m03arm.SPOT_SNAPSHOT_DOC_REL,
    m03arm.FUNDING_SNAPSHOT_DOC_REL,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_live(rel: str, dest_root: Path) -> None:
    src = REPO / rel
    dest = dest_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if rel in _UNUSED_ARM_RELS:
        data = subprocess.check_output(
            ["git", "-C", str(REPO), "show", f"{UNUSED_ARM_HEAD}:{rel}"]
        )
        dest.write_bytes(data)
        return
    shutil.copy2(src, dest)


def _bind(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(m03arm, "_repo_root", lambda: repo)


def _armed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel in _TRACKED:
        _copy_live(rel, repo)
    return repo


def _rewrite_json(path: Path, mutator) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_live_arm_is_consumed_and_refuses_rerun():
    assert derive_market_03_run_identity() == FROZEN_MARKET_03_RUN_IDENTITY
    with pytest.raises(Market03CanonicalExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_03_arm()
    with pytest.raises(Market03CanonicalExecutionNotAuthorized):
        authenticate_market_03_canonical_execution()
    payload = json.loads((REPO / m03arm.ARM_JSON_REL).read_text(encoding="utf-8"))
    for field in ARM_OUTCOME_FIELDS:
        assert field not in payload
    assert payload["run_identity"] == FROZEN_MARKET_03_RUN_IDENTITY
    assert payload["authorization_consumed"] is True
    assert payload["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert payload["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    unused = subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"{UNUSED_ARM_HEAD}:{m03arm.ARM_JSON_REL}"]
    )
    assert hashlib.sha256(unused).hexdigest() == ARM_JSON_SHA256
    state = inspect_market_03_arm_state()
    assert state["MARKET_03_EXECUTION_AUTHORIZED"] is False
    frozen = inspect_market_03_authorization_state()
    assert frozen["MARKET_03_ARMED"] is False
    assert frozen["CANONICAL_EXECUTIONS_AUTHORIZED"] == 0
    assert CANONICAL_EXECUTIONS_AUTHORIZED == 1
    assert CANONICAL_EXECUTIONS_CONSUMED == 0
    assert run_canonical_market_03() == 3


def test_frozen_scientific_and_prereg_and_freeze_bytes_unchanged():
    authenticate_frozen_prereg_bytes()
    authenticate_frozen_scientific_bytes()
    freeze = authenticate_market_03_implementation_freeze()
    assert freeze["sha256"] == IMPL_FREEZE_JSON_SHA256
    assert freeze["md_sha256"] == IMPL_FREEZE_MD_SHA256
    assert _sha256(REPO / m03arm.PREREG_MD_REL) == FROZEN_PREREG_MD_SHA256
    assert _sha256(REPO / m03arm.PREREG_JSON_REL) == FROZEN_PREREG_JSON_SHA256
    assert _sha256(REPO / m03arm.LIB_REL) == LIB_SHA256
    assert _sha256(REPO / m03arm.AUTHORITY_REL) == AUTHORITY_SHA256
    assert _sha256(REPO / m03arm.EXECUTE_REL) == EXECUTE_SHA256
    assert FROZEN_IMPLEMENTATION_HEAD == "03411aaa1a2f938169f07f8f3576f17227a2b14b"
    assert FROZEN_IMPLEMENTATION_TREE == "87a1da250a56343c44625e3f5187a6877035d1da"


def test_frozen_execute_stub_still_refuses():
    with pytest.raises(
        Exception,
        match="MARKET_03_CANONICAL_PATH_NOT_ARMED|MARKET_03_EXECUTION_NOT_AUTHORIZED",
    ):
        execute_bound_market_03()


def test_missing_arm_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    (repo / m03arm.ARM_JSON_REL).unlink()
    _bind(monkeypatch, repo)
    with pytest.raises(Market03CanonicalExecutionNotAuthorized, match="ARM_MISSING"):
        authenticate_market_03_arm()
    with pytest.raises(PreConsumptionBlocker):
        authenticate_pre_execution()
    state = inspect_market_03_arm_state()
    assert state["MARKET_03_ARMED"] is False


def test_wrong_arm_hash_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    path = repo / m03arm.ARM_JSON_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["date_utc"] = "1999-01-01"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _bind(monkeypatch, repo)
    with pytest.raises(Market03ArmAuthorityError, match="ARM_HASH_MISMATCH"):
        authenticate_market_03_arm()


def test_wrong_run_identity_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(repo / m03arm.ARM_JSON_REL, lambda p: p.update(run_identity="0" * 64))
    _bind(monkeypatch, repo)
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="RUN_IDENTITY"
    ):
        authenticate_market_03_arm()


def test_wrong_prereg_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    target = repo / m03arm.PREREG_JSON_REL
    target.write_bytes(target.read_bytes() + b"\n")
    _bind(monkeypatch, repo)
    with pytest.raises(Market03ArmAuthorityError, match="PREREG_BYTE_IDENTITY"):
        authenticate_market_03_arm()


def test_wrong_implementation_freeze_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    target = repo / m03arm.IMPL_FREEZE_JSON_REL
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["status"] = "TAMPERED"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _bind(monkeypatch, repo)
    with pytest.raises(Market03ArmAuthorityError, match="BYTE_IDENTITY"):
        authenticate_market_03_arm()


def test_modified_scientific_file_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    target = repo / m03arm.LIB_REL
    target.write_bytes(target.read_bytes() + b"\n# mutated\n")
    _bind(monkeypatch, repo)
    with pytest.raises(Market03ArmAuthorityError, match="BYTE_IDENTITY"):
        authenticate_market_03_arm()
    with pytest.raises(PreConsumptionBlocker):
        authenticate_pre_execution()


def test_wrong_external_commit_tree_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.ARM_JSON_REL,
        lambda p: p.update(external_commit="0" * 40, external_tree="0" * 40),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="EXTERNAL_COMMIT"
    ):
        authenticate_market_03_arm()


def test_wrong_spot_snapshot_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.ARM_JSON_REL,
        lambda p: p.update(spot_snapshot_id="0" * 64),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="SNAPSHOT"
    ):
        authenticate_market_03_arm()


def test_wrong_funding_snapshot_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.ARM_JSON_REL,
        lambda p: p.update(funding_snapshot_id="0" * 64),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="SNAPSHOT"
    ):
        authenticate_market_03_arm()


def test_wrong_spot_snapshot_doc_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.SPOT_SNAPSHOT_DOC_REL,
        lambda p: p.update(snapshot_id="0" * 64),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market03ArmAuthorityError, match="SPOT_SNAPSHOT"):
        authenticate_market_03_canonical_execution()


def test_wrong_funding_snapshot_doc_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.FUNDING_SNAPSHOT_DOC_REL,
        lambda p: p.update(snapshot_id="0" * 64),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market03ArmAuthorityError, match="FUNDING_SNAPSHOT"):
        authenticate_market_03_canonical_execution()


def test_b2_06_substitution_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.ARM_JSON_REL,
        lambda p: p.update(
            funding_dataset_id=m03arm.B2_06_DATASET_ID,
            funding_snapshot_id=B2_06_SNAPSHOT_ID,
        ),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market03ArmAuthorityError, match="B2_06"):
        authenticate_market_03_arm()


def test_authorized_zero_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.ARM_JSON_REL,
        lambda p: p.update(
            authorized_run_count=0,
            CANONICAL_EXECUTIONS_AUTHORIZED=0,
        ),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="AUTHORIZED"
    ):
        authenticate_market_03_arm()


def test_consumed_one_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.RESERVATION_JSON_REL,
        lambda p: p.update(CANONICAL_EXECUTIONS_CONSUMED=1),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="CONSUMED"
    ):
        authenticate_market_03_reservation()
    with pytest.raises(Market03CanonicalExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_03_canonical_execution()


def test_protected_oos_extension_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _rewrite_json(
        repo / m03arm.ARM_JSON_REL,
        lambda p: p.update(evaluation_end_exclusive="2026-01-01T00:00:00Z"),
    )
    _bind(monkeypatch, repo)
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="PROTECTED_OOS"
    ):
        authenticate_market_03_arm()
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="PROTECTED_OOS"
    ):
        reject_protected_oos_extension("2026-01-01T00:00:00Z")


def test_caller_kwargs_cannot_replace_authority():
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="caller arguments"
    ):
        authenticate_market_03_arm(run_identity="forged")
    with pytest.raises(
        Market03CanonicalExecutionNotAuthorized, match="caller arguments"
    ):
        derive_market_03_run_identity("forged")
    with pytest.raises(PreConsumptionBlocker, match="caller arguments"):
        authenticate_pre_execution(run_identity="forged")


def test_atomic_consume_then_second_run_fails(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    first = consume_authorization_atomically()
    assert first["CANONICAL_EXECUTIONS_CONSUMED"] == "1"
    reservation = json.loads((repo / m03arm.RESERVATION_JSON_REL).read_text())
    assert reservation["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert reservation["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    with pytest.raises(Market03CanonicalExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_03_canonical_execution()
    with pytest.raises(Market03CanonicalExecutionNotAuthorized, match="CONSUMED"):
        consume_authorization_atomically()
    live = json.loads((REPO / m03arm.RESERVATION_JSON_REL).read_text())
    assert live["CANONICAL_EXECUTIONS_CONSUMED"] == 1


def test_wrapper_reserved_stub_does_not_rerun_science():
    before = json.loads((REPO / m03arm.RESERVATION_JSON_REL).read_text())
    assert before["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    assert run_canonical_market_03() == 3
    after = json.loads((REPO / m03arm.RESERVATION_JSON_REL).read_text())
    assert after["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    with pytest.raises(
        Market03CanonicalExecutionReserved, match="RESERVED_FOR_EXECUTION_UNIT"
    ):
        evaluate_bound_after_arm_consumption(
            candles=None,
            funding=None,
            spot_snapshot_id=SPOT_SNAPSHOT_ID,
            funding_snapshot_id=FUNDING_SNAPSHOT_ID,
        )


def test_live_reservation_consumed_and_snapshot_ids_bound():
    with pytest.raises(Market03CanonicalExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_03_reservation()
    reservation = json.loads((REPO / m03arm.RESERVATION_JSON_REL).read_text())
    assert reservation["run_identity"] == FROZEN_MARKET_03_RUN_IDENTITY
    assert reservation["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert reservation["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    assert reservation["rerun_preauthorized"] is False
    arm = json.loads((REPO / m03arm.ARM_JSON_REL).read_text(encoding="utf-8"))
    assert arm["spot_snapshot_id"] == SPOT_SNAPSHOT_ID
    assert arm["funding_snapshot_id"] == FUNDING_SNAPSHOT_ID
    assert arm["b2_06_is_not_authority"] is True
