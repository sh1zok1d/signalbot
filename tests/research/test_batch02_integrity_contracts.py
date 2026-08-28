from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.research.b2_01_volatility_transition_lib import (
    rolling_midrank_percentile as frozen_b201_midrank,
)
from scripts.research.lib import batch02_contracts
from scripts.research.lib.batch02_contracts import (
    Batch02ContractError,
    Batch02RunContext,
    persist_batch02_result,
    prepare_batch02_run,
    rolling_midrank_percentile,
    verify_batch02_code,
)
from scripts.research.lib.research_harness import VerifiedCodeFreeze


def test_canonical_midrank_requires_full_finite_prior_window():
    values = np.asarray([1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0], dtype=np.float64)
    out = rolling_midrank_percentile(values, window=3)

    assert np.all(np.isnan(out[:3]))
    assert np.isnan(out[3])  # prior [1, 2, NaN]
    assert np.isnan(out[5])  # prior [NaN, 4, 5]
    assert out[6] == pytest.approx(1.0)  # prior [4, 5, 6], current 7


def test_canonical_midrank_excludes_current_and_future_and_uses_midrank_ties():
    values = np.asarray([5.0, 5.0, 5.0, 5.0, 999.0], dtype=np.float64)
    out1 = rolling_midrank_percentile(values, window=3)
    assert out1[3] == pytest.approx(0.5)

    changed_future = values.copy()
    changed_future[4] = -999.0
    out2 = rolling_midrank_percentile(changed_future, window=3)
    assert out2[3] == pytest.approx(out1[3])


def test_canonical_midrank_accepts_numpy_integral_window():
    values = np.asarray([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    out = rolling_midrank_percentile(values, window=np.int64(3))
    assert out[3] == pytest.approx(1.0)


def test_canonical_midrank_rejects_invalid_window_shape_and_coercion():
    with pytest.raises(Batch02ContractError, match="positive integer"):
        rolling_midrank_percentile(np.asarray([1.0, 2.0]), window=0)
    with pytest.raises(Batch02ContractError, match="positive integer"):
        rolling_midrank_percentile(np.asarray([1.0, 2.0]), window=True)
    with pytest.raises(Batch02ContractError, match="one-dimensional"):
        rolling_midrank_percentile(np.asarray([[1.0, 2.0]]), window=1)
    with pytest.raises(Batch02ContractError, match="coercible"):
        rolling_midrank_percentile(["not-a-number"], window=1)


def test_canonical_midrank_matches_frozen_b201_semantics():
    values = np.asarray(
        [1.0, 2.0, 2.0, 4.0, np.nan, 5.0, 6.0, 6.0, 9.0],
        dtype=np.float64,
    )
    expected = frozen_b201_midrank(values, window=3)
    actual = rolling_midrank_percentile(values, window=3)
    np.testing.assert_allclose(actual, expected, equal_nan=True)


def test_identity_verification_does_not_authorize_dataset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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


@pytest.mark.parametrize(
    "ack",
    [False, 0, 1, "true", np.bool_(True)],
)
def test_prepare_batch02_run_requires_literal_true_ack_before_authorization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ack,
):
    freeze = object.__new__(VerifiedCodeFreeze)

    def forbidden_authorize(**kwargs):
        raise AssertionError("dataset authorization must not run without literal True")

    monkeypatch.setattr(
        batch02_contracts, "authorize_dataset_access", forbidden_authorize
    )

    with pytest.raises(Batch02ContractError, match="explicit acknowledgement"):
        prepare_batch02_run(
            code_freeze=freeze,
            outcome_access_acknowledged=ack,
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    freeze = object.__new__(VerifiedCodeFreeze)
    monkeypatch.setattr(
        batch02_contracts.Batch02RunContext,
        "assert_minted",
        lambda self: None,
    )
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
    assert ctx._authorized_dataset is authorized
    assert ctx.run_identity == identity_payload
    assert ctx.run_identity is not identity_payload


def test_persist_batch02_result_reserves_then_writes_provenance_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    calls: list[tuple[Path, dict[str, object]]] = []

    def fake_write(path: Path, payload: dict[str, object]) -> str:
        calls.append((path, payload))
        return "d" * 64

    ctx = object.__new__(Batch02RunContext)
    object.__setattr__(
        ctx,
        "run_identity",
        {
            "hypothesis_id": "B2-02",
            "stage": "development",
            "proof": "canonical",
        },
    )
    object.__setattr__(ctx, "_run_identity_sha256", "e" * 64)
    object.__setattr__(ctx, "code_freeze", SimpleNamespace(repo_root=tmp_path))

    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)
    monkeypatch.setattr(batch02_contracts, "write_json_new", fake_write)

    target = tmp_path / "artifacts" / "b2_02" / "B2_02_DEV_RESULTS.json"
    digest = persist_batch02_result(
        target,
        {"status": "closed"},
        run_context=ctx,
    )

    assert digest == "d" * 64
    assert len(calls) == 2
    lock_path, lock_payload = calls[0]
    assert lock_path.parent == (
        tmp_path / "artifacts" / "b2_02" / ".batch02_evidence_locks"
    )
    assert lock_payload["artifact_kind"] == "batch02_logical_result_reservation"
    assert lock_payload["logical_result_path"] == str(target.resolve(strict=False))
    assert lock_payload["run_identity_sha256"] == "e" * 64
    assert calls[1] == (
        target,
        {
            "status": "closed",
            "provenance": {
                "hypothesis_id": "B2-02",
                "stage": "development",
                "proof": "canonical",
            },
        },
    )


def test_persist_rejects_caller_supplied_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    ctx = object.__new__(Batch02RunContext)
    object.__setattr__(
        ctx,
        "run_identity",
        {
            "hypothesis_id": "B2-02",
            "stage": "development",
            "proof": "canonical",
        },
    )
    object.__setattr__(ctx, "_run_identity_sha256", "e" * 64)
    object.__setattr__(ctx, "code_freeze", SimpleNamespace(repo_root=tmp_path))
    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)

    with pytest.raises(Batch02ContractError, match="must not supply provenance"):
        persist_batch02_result(
            tmp_path / "artifacts" / "b2_02" / "B2_02_DEV_RESULTS.json",
            {"provenance": {"proof": "forged"}},
            run_context=ctx,
        )


def test_persist_rejects_cross_hypothesis_result_filename(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    ctx = object.__new__(Batch02RunContext)
    object.__setattr__(
        ctx,
        "run_identity",
        {
            "hypothesis_id": "B2-02",
            "stage": "development",
            "proof": "canonical",
        },
    )
    object.__setattr__(ctx, "_run_identity_sha256", "e" * 64)
    object.__setattr__(ctx, "code_freeze", SimpleNamespace(repo_root=tmp_path))
    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)

    wrong = (
        tmp_path / "artifacts" / "b2_03" / "B2_03_DEV_RESULTS.json"
    )
    with pytest.raises(Batch02ContractError, match="not bound to run identity"):
        persist_batch02_result(
            wrong,
            {"status": "closed"},
            run_context=ctx,
        )

    assert not wrong.exists()
    assert not (
        tmp_path / "artifacts" / "b2_03" / ".batch02_evidence_locks"
    ).exists()


def test_persist_rejects_second_directory_for_same_run_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    ctx = object.__new__(Batch02RunContext)
    object.__setattr__(
        ctx,
        "run_identity",
        {
            "hypothesis_id": "B2-02",
            "stage": "development",
            "proof": "canonical",
        },
    )
    object.__setattr__(ctx, "_run_identity_sha256", "e" * 64)
    object.__setattr__(ctx, "code_freeze", SimpleNamespace(repo_root=tmp_path))
    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)

    alternate = (
        tmp_path / "alternate" / "b2_02" / "B2_02_DEV_RESULTS.json"
    )
    with pytest.raises(Batch02ContractError, match="not bound to run identity"):
        persist_batch02_result(
            alternate,
            {"status": "closed"},
            run_context=ctx,
        )

    assert not alternate.exists()
