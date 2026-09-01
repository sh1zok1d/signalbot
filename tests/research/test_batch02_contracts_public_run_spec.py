from __future__ import annotations

from pathlib import Path

import pytest

from scripts.research.lib import batch02_contracts as contracts
from scripts.research.lib.research_harness import (
    DatasetIdentityContract,
    OutcomeAccessPolicy,
    PromotionGateContract,
)


def test_prepare_public_primitive_form_builds_internal_contracts(monkeypatch, tmp_path: Path):
    captured = {}

    class Freeze:
        repo_root = tmp_path
        code_sha = "abc"
        tree_oid = "tree"

    monkeypatch.setattr(contracts, "VerifiedCodeFreeze", Freeze)

    class Authorized:
        def assert_minted(self):
            return None

    monkeypatch.setattr(contracts, "AuthorizedDataset", Authorized)

    def fake_authorize_dataset_access(*, code_freeze, dataset_root, identity, policy):
        captured["identity"] = identity
        captured["policy"] = policy
        return Authorized()

    def fake_build_run_identity(*, gate_contract, **kwargs):
        captured["gates"] = gate_contract
        return {
            "hypothesis_id": kwargs["hypothesis_id"],
            "stage": kwargs["stage"],
            "dataset_id": captured["identity"].dataset_id,
        }

    monkeypatch.setattr(
        contracts, "authorize_dataset_access", fake_authorize_dataset_access
    )
    monkeypatch.setattr(contracts, "build_run_identity", fake_build_run_identity)

    ctx = contracts.prepare_batch02_run(
        code_freeze=Freeze(),
        outcome_access_acknowledged=True,
        dataset_root=tmp_path,
        dataset_id="CORE",
        snapshot_id="snap",
        start_inclusive_ms=1_577_836_800_000,
        end_exclusive_ms=1_735_689_600_000,
        allowed_years=(2020, 2021, 2022, 2023, 2024),
        required_gate_names=("g1", "g2"),
        hypothesis_id="B2-02_TEST",
        stage="development",
        command=("python", "-m", "test"),
        seeds={"x": 1},
    )

    assert isinstance(captured["identity"], DatasetIdentityContract)
    assert isinstance(captured["policy"], OutcomeAccessPolicy)
    assert isinstance(captured["gates"], PromotionGateContract)
    assert captured["gates"].required_gate_names == ("g1", "g2")
    assert ctx.run_identity["hypothesis_id"] == "B2-02_TEST"


def test_prepare_rejects_mixed_contract_forms(monkeypatch, tmp_path: Path):
    class Freeze:
        repo_root = tmp_path
        code_sha = "abc"
        tree_oid = "tree"

    monkeypatch.setattr(contracts, "VerifiedCodeFreeze", Freeze)
    identity = DatasetIdentityContract(dataset_id="CORE", snapshot_id="snap")
    policy = OutcomeAccessPolicy(
        stage="development",
        start_inclusive_ms=1_577_836_800_000,
        end_exclusive_ms=1_735_689_600_000,
        allowed_years=(2020, 2021, 2022, 2023, 2024),
    )
    gates = PromotionGateContract(required_gate_names=("g1",))

    with pytest.raises(contracts.Batch02ContractError, match="may not mix"):
        contracts.prepare_batch02_run(
            code_freeze=Freeze(),
            outcome_access_acknowledged=True,
            dataset_root=tmp_path,
            identity=identity,
            policy=policy,
            gate_contract=gates,
            dataset_id="CORE",
            hypothesis_id="B2-02_TEST",
            stage="development",
            command=("python",),
            seeds={},
        )
