from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from scripts.research.b2_01_volatility_transition_lib import (
    rolling_midrank_percentile as frozen_b201_midrank,
)
from scripts.research.lib import batch02_contracts
from scripts.research.lib.batch02_contracts import (
    Batch02ContractError,
    persist_batch02_result,
    prepare_batch02_run,
    rolling_midrank_percentile,
    verify_batch02_code,
)
from scripts.research.lib.research_harness import VerifiedCodeFreeze


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = REPO_ROOT / "scripts" / "research"
FROZEN_B201_RUNNER = "b2_01_volatility_transition.py"
FROZEN_B201_LIB = "b2_01_volatility_transition_lib.py"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def _imported_from(tree: ast.AST, module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


def _batch02_runtime_files() -> list[Path]:
    return sorted(RESEARCH_DIR.rglob("b2_[0-9][0-9]_*.py"))


def test_canonical_midrank_requires_full_finite_prior_window():
    values = np.asarray([1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0], dtype=np.float64)
    out = rolling_midrank_percentile(values, window=3)

    assert np.all(np.isnan(out[:3]))
    # Reference for i=3 is [1, 2, NaN] -> unavailable.
    assert np.isnan(out[3])
    # Reference for i=5 is [NaN, 4, 5] -> unavailable.
    assert np.isnan(out[5])
    # Reference for i=6 is [4, 5, 6], current=7 -> strict upper rank.
    assert out[6] == pytest.approx(1.0)


def test_canonical_midrank_excludes_current_and_future_and_uses_midrank_ties():
    values = np.asarray([5.0, 5.0, 5.0, 5.0, 999.0], dtype=np.float64)
    out1 = rolling_midrank_percentile(values, window=3)
    assert out1[3] == pytest.approx(0.5)

    changed_future = values.copy()
    changed_future[4] = -999.0
    out2 = rolling_midrank_percentile(changed_future, window=3)
    assert out2[3] == pytest.approx(out1[3])


def test_canonical_midrank_rejects_invalid_shape_and_window():
    with pytest.raises(Batch02ContractError, match="positive integer"):
        rolling_midrank_percentile(np.asarray([1.0, 2.0]), window=0)
    with pytest.raises(Batch02ContractError, match="positive integer"):
        rolling_midrank_percentile(np.asarray([1.0, 2.0]), window=True)
    with pytest.raises(Batch02ContractError, match="one-dimensional"):
        rolling_midrank_percentile(np.asarray([[1.0, 2.0]]), window=1)


def test_canonical_midrank_matches_frozen_b201_semantics():
    # B2-01 is already outcome-consumed and must not be rewritten merely for
    # deduplication. Prove the new canonical primitive matches its strict
    # semantics instead.
    values = np.asarray(
        [1.0, 2.0, 2.0, 4.0, np.nan, 5.0, 6.0, 6.0, 9.0],
        dtype=np.float64,
    )
    expected = frozen_b201_midrank(values, window=3)
    actual = rolling_midrank_percentile(values, window=3)
    np.testing.assert_allclose(actual, expected, equal_nan=True)


def test_identity_verification_does_not_authorize_dataset(monkeypatch, tmp_path: Path):
    sentinel = object()
    calls: list[str] = []

    def fake_verify(repo_root: Path, expected_sha: str):
        calls.append("verify")
        assert repo_root == tmp_path
        assert expected_sha == "a" * 40
        return sentinel

    def forbidden_authorize(**kwargs):
        raise AssertionError("identity stage must not authorize dataset")

    monkeypatch.setattr(batch02_contracts, "verify_git_freeze", fake_verify)
    monkeypatch.setattr(
        batch02_contracts, "authorize_dataset_access", forbidden_authorize
    )

    result = verify_batch02_code(
        repo_root=tmp_path,
        expected_code_sha="a" * 40,
    )
    assert result is sentinel
    assert calls == ["verify"]


def test_prepare_batch02_run_rejects_identity_stage_before_authorization(
    monkeypatch, tmp_path: Path
):
    freeze = object.__new__(VerifiedCodeFreeze)

    def forbidden_authorize(**kwargs):
        raise AssertionError("identity stage must never authorize dataset")

    monkeypatch.setattr(
        batch02_contracts, "authorize_dataset_access", forbidden_authorize
    )

    with pytest.raises(Batch02ContractError, match="restricted to development"):
        prepare_batch02_run(
            code_freeze=freeze,
            outcome_access_acknowledged=True,
            dataset_root=tmp_path,
            identity=object(),
            policy=object(),
            gate_contract=object(),
            hypothesis_id="B2-XX",
            stage="identity",
            command=("python", "-m", "x"),
            seeds={},
        )


def test_prepare_batch02_run_requires_explicit_outcome_ack_before_authorization(
    monkeypatch, tmp_path: Path
):
    freeze = object.__new__(VerifiedCodeFreeze)

    def forbidden_authorize(**kwargs):
        raise AssertionError("dataset authorization must not run without ack")

    monkeypatch.setattr(
        batch02_contracts, "authorize_dataset_access", forbidden_authorize
    )

    with pytest.raises(Batch02ContractError, match="explicit acknowledgement"):
        prepare_batch02_run(
            code_freeze=freeze,
            outcome_access_acknowledged=False,
            dataset_root=tmp_path,
            identity=object(),
            policy=object(),
            gate_contract=object(),
            hypothesis_id="B2-XX",
            stage="development",
            command=("python", "-m", "x"),
            seeds={},
        )


def test_prepare_batch02_run_orders_authorization_before_identity_build(
    monkeypatch, tmp_path: Path
):
    freeze = object.__new__(VerifiedCodeFreeze)
    authorized = object()
    identity_payload = {"proof": "ok"}
    calls: list[str] = []

    def fake_authorize(**kwargs):
        calls.append("authorize")
        assert kwargs["code_freeze"] is freeze
        assert kwargs["dataset_root"] == tmp_path
        return authorized

    def fake_build(**kwargs):
        calls.append("identity")
        assert kwargs["code_freeze"] is freeze
        assert kwargs["authorized_dataset"] is authorized
        return identity_payload

    monkeypatch.setattr(batch02_contracts, "authorize_dataset_access", fake_authorize)
    monkeypatch.setattr(batch02_contracts, "build_run_identity", fake_build)

    ctx = prepare_batch02_run(
        code_freeze=freeze,
        outcome_access_acknowledged=True,
        dataset_root=tmp_path,
        identity=object(),
        policy=object(),
        gate_contract=object(),
        hypothesis_id="B2-XX",
        stage="development",
        command=("python", "-m", "x"),
        seeds={"bootstrap": 1},
    )

    assert calls == ["authorize", "identity"]
    assert ctx.code_freeze is freeze
    assert ctx.authorized_dataset is authorized
    assert ctx.run_identity is identity_payload


def test_persist_batch02_result_reserves_then_writes_immutably(
    monkeypatch, tmp_path: Path
):
    calls: list[tuple[Path, dict[str, object]]] = []

    def fake_write(path: Path, payload: dict[str, object]) -> str:
        calls.append((path, payload))
        return "d" * 64

    monkeypatch.setattr(batch02_contracts, "write_json_new", fake_write)
    target = tmp_path / "result.json"
    digest = persist_batch02_result(target, {"status": "closed"})

    assert digest == "d" * 64
    assert len(calls) == 2
    lock_path, lock_payload = calls[0]
    assert lock_path.parent == tmp_path / ".batch02_evidence_locks"
    assert lock_payload["artifact_kind"] == "batch02_logical_result_reservation"
    assert lock_payload["logical_result_path"] == str(target.resolve(strict=False))
    assert calls[1] == (target, {"status": "closed"})


def test_frozen_b201_runner_already_uses_fail_closed_harness_path():
    path = RESEARCH_DIR / FROZEN_B201_RUNNER
    tree = _parse(path)
    calls = _call_names(tree)

    assert {"verify_git_freeze", "authorize_dataset_access", "write_json_new"} <= calls
    assert "_git_sha" not in {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    assert "write_text" not in calls
    assert "write_bytes" not in calls



def test_b202_plus_files_cannot_reintroduce_batch01_identity_or_persistence():
    for path in _batch02_runtime_files():
        if path.name in {FROZEN_B201_RUNNER, FROZEN_B201_LIB}:
            continue

        tree = _parse(path)
        calls = _call_names(tree)
        function_defs = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }

        assert "_git_sha" not in function_defs, (
            f"{path.name} may not reintroduce fallback Git identity"
        )
        assert "write_text" not in calls and "write_bytes" not in calls, (
            f"{path.name} may not overwrite evidence with Path.write_*"
        )
        assert "open" not in calls, (
            f"{path.name} may not perform ad-hoc runtime file I/O"
        )


def test_b202_plus_runners_must_use_canonical_contract_layer():
    for path in _batch02_runtime_files():
        if path.name == FROZEN_B201_RUNNER or path.name.endswith("_lib.py"):
            continue

        tree = _parse(path)
        imported = _imported_from(
            tree, "scripts.research.lib.batch02_contracts"
        )
        calls = _call_names(tree)
        function_defs = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }

        required = {
            "verify_batch02_code",
            "prepare_batch02_run",
            "persist_batch02_result",
        }
        assert required <= imported, (
            f"{path.name} must import canonical Batch02 integrity entry points"
        )
        assert required <= calls, (
            f"{path.name} must call canonical Batch02 integrity entry points"
        )

        assert "_git_sha" not in function_defs, (
            f"{path.name} may not reintroduce fallback Git identity"
        )
        assert "write_text" not in calls and "write_bytes" not in calls, (
            f"{path.name} may not overwrite evidence with Path.write_*"
        )
        assert "open" not in calls, (
            f"{path.name} may not perform ad-hoc runner file I/O"
        )

        direct_harness = _imported_from(
            tree, "scripts.research.lib.research_harness"
        )
        forbidden_direct = {
            "verify_git_freeze",
            "authorize_dataset_access",
            "write_json_new",
        }
        assert not (direct_harness & forbidden_direct), (
            f"{path.name} bypasses canonical Batch02 contract layer: "
            f"{sorted(direct_harness & forbidden_direct)}"
        )


def test_b202_plus_libs_cannot_define_hypothesis_specific_midrank():
    for path in _batch02_runtime_files():
        if path.name == FROZEN_B201_LIB or not path.name.endswith("_lib.py"):
            continue

        tree = _parse(path)
        function_defs = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        assert "rolling_midrank_percentile" not in function_defs, (
            f"{path.name} must import the canonical Batch02 midrank helper"
        )

        source = path.read_text(encoding="utf-8").lower()
        if "midrank" in source:
            imported = _imported_from(
                tree, "scripts.research.lib.batch02_contracts"
            )
            assert "rolling_midrank_percentile" in imported, (
                f"{path.name} mentions midrank but does not import the canonical helper"
            )


def test_batch02_parquet_reads_are_restricted_to_authorized_partition_proof():
    # Any direct parquet read in a B2 library must occur in the same function
    # that re-verifies AuthorizedDataset.list_monthly_partitions(). A library
    # may instead delegate loading to a shared authorized loader and then has
    # no direct parquet call to inspect here.
    for path in _batch02_runtime_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = _call_names(node)
            if not ({"read_table", "read_parquet"} & calls):
                continue
            assert "list_monthly_partitions" in calls, (
                f"{path.name}:{node.name} reads parquet without re-verifying "
                "AuthorizedDataset partition checksums"
            )
