"""Synthetic tests for the Sprint 02 D7 one-shot freeze.

No real CORE scientific target is computed. Evaluator fixtures are synthetic.
"""

from __future__ import annotations

import inspect
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.research import discovery_sprint_02_d7_one_shot as OS
from scripts.research import discovery_sprint_02_impl as I


REPO = Path(__file__).resolve().parents[2]

_COPY_RELS = (
    OS.PERMIT_REL,
    OS.REVIEW_JSON_REL,
    OS.FEASIBILITY_JSON_REL,
    I.SPRINT_JSON_REL,
    OS.IMPL_REL,
    OS.FEAS_CLI_REL,
    OS.RUNNER_REL,
    I.CORE_BTC_SNAPSHOT_DOC_REL,
    I.CORE_BTC_MANIFEST_REL,
)


def _copy_repo_tree(tmp_path: Path) -> Path:
    for rel in _COPY_RELS:
        src = REPO / rel
        if not src.is_file():
            pytest.skip(f"missing authority file {rel}")
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return tmp_path


def _ms(year: int, month: int = 1, day: int = 1, hour: int = 0) -> int:
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() * 1000)


def _hour(start_ms: int, year: int) -> I.HourBar:
    return I.HourBar(
        hour_start_ms=start_ms,
        available_at_ms=start_ms + I.HOUR_MS,
        year=year,
        open_1h=100.0,
        close_1h=101.0,
        quote_volume_1h=10.0,
        trade_count_1h=10,
        taker_buy_quote_volume_1h=4.0,
        ret_abs_1h=0.01,
        event_return=0.01,
    )


def _state(
    start_ms: int,
    year: int,
    *,
    d7_state: bool | None,
    rv_bucket: int | None = 0,
) -> I.D7HourState:
    return I.D7HourState(
        hour=_hour(start_ms, year),
        qrel_1h=1.0,
        impact_proxy=1.0,
        d7_state=d7_state,
        rv_bucket=rv_bucket,
    )


def test_import_does_not_execute_science():
    source = Path(OS.__file__).read_text(encoding="utf-8")
    assert "if __name__" in source
    assert "execute_one_shot()" not in inspect.getsource(OS.main)
    OS.assert_runner_has_no_d8_route()


def test_main_without_write_freeze_refuses_execution():
    with pytest.raises(SystemExit, match="D7_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"):
        OS.main([])


def test_permit_matches_recomputed_authority():
    stored = json.loads((REPO / OS.PERMIT_REL).read_text(encoding="utf-8"))
    expected = OS.expected_permit(REPO)
    assert stored == expected
    raw = (REPO / OS.PERMIT_REL).read_text(encoding="utf-8")
    assert raw == I.canonical_json(expected)


def test_verify_tracked_permit_on_live_tree():
    stored = OS.verify_tracked_permit(REPO)
    assert stored["EXECUTION_AUTHORIZED"] is True
    assert stored["ONE_SHOT"] is True
    assert stored["RERUN_AUTHORIZED"] is False
    assert stored["D7_SELECTOR_N"] == 4545
    assert stored["D7_SELECTOR_DIGEST"] == I.D7_SELECTOR_DIGEST
    assert stored["CORE_BTC_SNAPSHOT_ID"] == I.CORE_BTC_SNAPSHOT_ID
    assert stored["DATA_IDENTITY_MODE"] == I.DATA_IDENTITY_MODE
    assert stored["D8_SCIENTIFIC_EXECUTION_ELIGIBLE"] is False
    assert stored["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert stored["ONE_SHOT_RUNNER_SHA256"] == OS.current_runner_sha256(REPO)
    hashes = OS.current_authority_hashes(REPO)
    assert hashes["DISCOVERY_SPRINT_02_SHA256"] == OS.FROZEN_DISCOVERY_SPRINT_02_SHA256
    assert hashes["FEASIBILITY_JSON_SHA256"] == OS.FROZEN_FEASIBILITY_JSON_SHA256
    assert (
        hashes["IMPLEMENTATION_REVIEW_JSON_SHA256"]
        == OS.FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256
    )
    assert (
        hashes["REVIEWED_IMPLEMENTATION_SHA256"]
        == OS.FROZEN_REVIEWED_IMPLEMENTATION_SHA256
    )
    assert hashes["FEASIBILITY_CLI_SHA256"] == OS.FROZEN_FEASIBILITY_CLI_SHA256
    assert hashes["FEASIBILITY_ARTIFACT_SHA256"] == OS.FROZEN_FEASIBILITY_ARTIFACT_SHA256


@pytest.mark.parametrize(
    "rel,token",
    [
        (OS.IMPL_REL, "\n# mutated-implementation-byte\n"),
        (OS.REVIEW_JSON_REL, None),
        (OS.FEASIBILITY_JSON_REL, None),
    ],
)
def test_moved_authority_bytes_fail_permit_verify(tmp_path, rel, token):
    repo = _copy_repo_tree(tmp_path)
    path = repo / rel
    if token is None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["STATUS"] = "TAMPERED"
        path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        path.write_text(path.read_text(encoding="utf-8") + token, encoding="utf-8")
    with pytest.raises(OS.OneShotExecutionError):
        OS.verify_tracked_permit(repo)


def test_changed_core_snapshot_identity_fails(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    path = repo / I.CORE_BTC_SNAPSHOT_DOC_REL
    identity = json.loads(path.read_text(encoding="utf-8"))
    identity["snapshot_id"] = "0" * 64
    path.write_text(json.dumps(identity), encoding="utf-8")
    with pytest.raises(I.SnapshotIdentityError):
        OS.verify_pre_scientific_authorities(repo)


def test_changed_manifest_authorization_fails(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    path = repo / I.CORE_BTC_MANIFEST_REL
    text = path.read_text(encoding="utf-8")
    text = text.replace("research_authorized: true", "research_authorized: false", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(I.SnapshotIdentityError):
        OS.verify_pre_scientific_authorities(repo)


def test_protected_path_refused():
    with pytest.raises(I.ProtectedYearRefused):
        I.legal_monthly_parquet_path(Path("/tmp/ds"), "2025-01")
    with pytest.raises(I.ProtectedYearRefused):
        I.legal_monthly_parquet_path(Path("/tmp/ds"), "2026-06")


@pytest.mark.parametrize(
    "field,value",
    [
        ("SELECTOR_N", I.D7_SELECTOR_N + 1),
        ("SELECTOR_DIGEST", "0" * 64),
        ("CONSTRUCTED_HOURS", I.D7_CONSTRUCTED_HOURS + 1),
        ("VALID_IMPACT_ROWS", I.D7_VALID_IMPACT_ROWS + 1),
        ("TARGET_ELIGIBLE_ROWS", I.D7_TARGET_ELIGIBLE_ROWS + 1),
    ],
)
def test_selector_identity_mismatch_fails_before_outcome(field, value):
    session = OS.D7OneShotSession()
    census = {
        "SELECTOR_N": I.D7_SELECTOR_N,
        "SELECTOR_DIGEST": I.D7_SELECTOR_DIGEST,
        "CONSTRUCTED_HOURS": I.D7_CONSTRUCTED_HOURS,
        "VALID_IMPACT_ROWS": I.D7_VALID_IMPACT_ROWS,
        "TARGET_ELIGIBLE_ROWS": I.D7_TARGET_ELIGIBLE_ROWS,
        "SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
    }
    census[field] = value
    with pytest.raises((I.SelectorIdentityError, I.RealScientificOutcomeForbidden)):
        I.assert_d7_selector_identity(census)
    assert session.identity_ok is False
    with pytest.raises(OS.TargetBeforeIdentityError):
        OS.construct_d7_scientific_arrays([], session=session)


def test_selector_identity_recompute_does_not_inspect_tplus1_boolean():
    start = _ms(2021, 3, 1)
    def _triple(last_state: bool) -> list[I.D7HourState]:
        return [
            _state(start, 2021, d7_state=False),
            _state(start + I.HOUR_MS, 2021, d7_state=True),
            _state(start + 2 * I.HOUR_MS, 2021, d7_state=last_state),
        ]
    census_a = I.d7_feasibility_census(_triple(True))
    census_b = I.d7_feasibility_census(_triple(False))
    assert census_a["SELECTOR_DIGEST"] == census_b["SELECTOR_DIGEST"]
    assert census_a["SELECTOR_N"] == census_b["SELECTOR_N"]
    assert census_a["SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED"] is False
    src = inspect.getsource(OS.reconstruct_d7_selector_identity)
    assert "evaluate_d7_scientific" not in src
    assert "construct_d7_scientific_arrays" not in src
    census_src = inspect.getsource(I.d7_feasibility_census)
    assert "d7_state is not None" in census_src
    assert "MU_D7_RULE" not in census_src


def test_target_and_evaluator_cannot_run_before_identity_gate():
    session = OS.D7OneShotSession()
    with pytest.raises(OS.TargetBeforeIdentityError):
        OS.construct_d7_scientific_arrays([], session=session)
    with pytest.raises(OS.OneShotExecutionError, match="EVALUATOR_BEFORE_IDENTITY"):
        OS.call_reviewed_d7_evaluator(
            {
                "candidate": [True],
                "target": [True],
                "year": [2020],
                "rv_bucket": [0],
                "target_eligible": [True],
            },
            session=session,
        )
    execute_src = inspect.getsource(OS.execute_one_shot)
    assert execute_src.index("reconstruct_d7_selector_identity") < execute_src.index(
        "construct_d7_scientific_arrays"
    )
    assert execute_src.index("construct_d7_scientific_arrays") < execute_src.index(
        "call_reviewed_d7_evaluator"
    )


def test_authority_failure_produces_no_result(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    path = repo / OS.PERMIT_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["REVIEWED_IMPLEMENTATION_SHA256"] = "0" * 64
    path.write_text(I.canonical_json(payload), encoding="utf-8")
    with pytest.raises(OS.OneShotExecutionError):
        OS.execute_one_shot(repo)
    assert not (repo / OS.RESULT_JSON_REL).exists()
    assert not (repo / OS.RESULT_MD_REL).exists()


def test_existing_result_refuses_execution(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    (repo / OS.RESULT_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / OS.RESULT_JSON_REL).write_text("{}", encoding="utf-8")
    with pytest.raises(OS.OneShotExecutionError, match="RESULT_ALREADY_EXISTS"):
        OS.execute_one_shot(repo)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("ONE_SHOT", False, "ONE_SHOT"),
        ("RERUN_AUTHORIZED", True, "RERUN"),
        ("EXECUTION_AUTHORIZED", False, "EXECUTION"),
    ],
)
def test_permit_lifecycle_flags_fail_closed(tmp_path, field, value, match):
    repo = _copy_repo_tree(tmp_path)
    path = repo / OS.PERMIT_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(I.canonical_json(payload), encoding="utf-8")
    with pytest.raises(OS.OneShotExecutionError):
        OS.verify_tracked_permit(repo)


def test_changed_permit_byte_fails(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    path = repo / OS.PERMIT_REL
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(OS.OneShotExecutionError):
        OS.verify_tracked_permit(repo)


def _gate_arrays(*, candidate_on: bool, target_on: bool, years=(2020, 2021, 2022, 2023, 2024)):
    candidate: list[bool] = []
    target: list[float] = []
    year: list[int] = []
    buckets: list[int] = []
    eligible: list[bool] = []
    for y in years:
        for j in range(20):
            year.append(y)
            buckets.append(0)
            eligible.append(True)
            is_cand = candidate_on and j == 0
            candidate.append(is_cand)
            if is_cand:
                target.append(1.0 if target_on else 0.01)
            else:
                target.append(0.0)
    return candidate, target, year, buckets, eligible


def test_synthetic_evaluator_promising_prototype():
    candidate, target, year, buckets, eligible = _gate_arrays(
        candidate_on=True, target_on=True
    )
    out = I.evaluate_d7_scientific(
        candidate=candidate,
        target=target,
        year=year,
        rv_bucket=buckets,
        target_eligible=eligible,
        n_replicates=200,
    )
    assert out["CLASSIFICATION"] == "D7_PROMISING_PROTOTYPE"
    assert out["STATISTICAL_GATE"] is True
    assert out["PRACTICAL_GATE"] is True
    assert out["TEMPORAL_GATE"] is True


def test_synthetic_evaluator_practical_fail_is_no_useful_structure():
    candidate, target, year, buckets, eligible = _gate_arrays(
        candidate_on=True, target_on=False
    )
    out = I.evaluate_d7_scientific(
        candidate=candidate,
        target=target,
        year=year,
        rv_bucket=buckets,
        target_eligible=eligible,
        n_replicates=200,
    )
    assert out["PRACTICAL_GATE"] is False
    assert out["CLASSIFICATION"] == "D7_NO_USEFUL_STRUCTURE"


def test_synthetic_evaluator_temporal_fail_is_no_useful_structure():
    candidate, target, year, buckets, eligible = _gate_arrays(
        candidate_on=True, target_on=True, years=(2020, 2021)
    )
    # remaining years exist but with no candidate / zero delta
    for y in (2022, 2023, 2024):
        for j in range(20):
            year.append(y)
            buckets.append(0)
            eligible.append(True)
            candidate.append(False)
            target.append(0.0)
    out = I.evaluate_d7_scientific(
        candidate=candidate,
        target=target,
        year=year,
        rv_bucket=buckets,
        target_eligible=eligible,
        n_replicates=200,
    )
    assert out["TEMPORAL_GATE"] is False
    assert out["CLASSIFICATION"] == "D7_NO_USEFUL_STRUCTURE"


def test_synthetic_null_fixture_is_no_useful_structure():
    n = 20
    out = I.evaluate_d7_scientific(
        candidate=[False] * n,
        target=[0.0] * n,
        year=[2020] * n,
        rv_bucket=[0] * n,
        target_eligible=[True] * n,
        n_replicates=20,
    )
    assert out["CLASSIFICATION"] == "D7_NO_USEFUL_STRUCTURE"


def test_synthetic_evaluator_pcg64_deterministic():
    candidate, target, year, buckets, eligible = _gate_arrays(
        candidate_on=True, target_on=True
    )
    first = I.evaluate_d7_scientific(
        candidate=candidate,
        target=target,
        year=year,
        rv_bucket=buckets,
        target_eligible=eligible,
        seed=I.D7_SEED,
        n_replicates=200,
    )
    second = I.evaluate_d7_scientific(
        candidate=candidate,
        target=target,
        year=year,
        rv_bucket=buckets,
        target_eligible=eligible,
        seed=I.D7_SEED,
        n_replicates=200,
    )
    assert first["MC_P_D7"] == second["MC_P_D7"]
    assert first["MU_D7_CONTROL"] == second["MU_D7_CONTROL"]
    assert first["CONTROL_D7_P95"] == second["CONTROL_D7_P95"]
    assert I.D7_SEED == 20260922171


def test_gated_evaluator_uses_reviewed_function_once():
    session = OS.D7OneShotSession()
    session.identity_ok = True
    session.target_constructed = True
    candidate, target, year, buckets, eligible = _gate_arrays(
        candidate_on=True, target_on=True
    )
    arrays = {
        "candidate": candidate,
        "target": target,
        "year": year,
        "rv_bucket": buckets,
        "target_eligible": eligible,
    }
    first = OS.call_reviewed_d7_evaluator(arrays, session=session)
    assert first["CLASSIFICATION"] in {
        "D7_PROMISING_PROTOTYPE",
        "D7_NO_USEFUL_STRUCTURE",
    }
    with pytest.raises(OS.OneShotExecutionError, match="ALREADY_CALLED"):
        OS.call_reviewed_d7_evaluator(arrays, session=session)


def test_d8_cannot_be_executed_through_runner():
    OS.assert_runner_has_no_d8_route()
    source = inspect.getsource(OS)
    assert "evaluate_d8" + "_scientific(" not in source
    assert "recovery_" + "6h(" not in inspect.getsource(OS.execute_one_shot)
    assert not hasattr(OS, "execute_d8")


def test_execute_one_shot_mocked_does_not_open_protected_years(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    session_holder: dict[str, OS.D7OneShotSession] = {}

    def fake_load(**kwargs):
        return []

    def fake_hours(_bars):
        return []

    def fake_states(_hours):
        return []

    def fake_reconstruct(states, *, session=None):
        if session is not None:
            session.identity_ok = True
            session_holder["session"] = session
        return {
            "SELECTOR_N": I.D7_SELECTOR_N,
            "SELECTOR_DIGEST": I.D7_SELECTOR_DIGEST,
            "CONSTRUCTED_HOURS": I.D7_CONSTRUCTED_HOURS,
            "VALID_IMPACT_ROWS": I.D7_VALID_IMPACT_ROWS,
            "TARGET_ELIGIBLE_ROWS": I.D7_TARGET_ELIGIBLE_ROWS,
            "SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED": False,
        }

    def fake_arrays(states, *, session=None):
        if session is None or session.identity_ok is not True:
            raise OS.TargetBeforeIdentityError("TARGET_BEFORE_IDENTITY_GATE")
        session.target_constructed = True
        candidate, target, year, buckets, eligible = _gate_arrays(
            candidate_on=True, target_on=True
        )
        return {
            "candidate": candidate,
            "target": target,
            "year": year,
            "rv_bucket": buckets,
            "target_eligible": eligible,
        }

    with patch.object(I, "load_legal_1m_bars", side_effect=fake_load), patch.object(
        I, "aggregate_completed_hours", side_effect=fake_hours
    ), patch.object(I, "build_d7_states", side_effect=fake_states), patch.object(
        OS, "reconstruct_d7_selector_identity", side_effect=fake_reconstruct
    ), patch.object(
        OS, "construct_d7_scientific_arrays", side_effect=fake_arrays
    ), patch.object(
        OS, "_git", return_value="deadbeef"
    ):
        result = OS.execute_one_shot(repo)
    assert result["SCIENTIFIC_OUTCOMES_COMPUTED"] is True
    assert result["PROTECTED_2025_OPENED"] is False
    assert result["PROTECTED_2026_OPENED"] is False
    assert result["D8_EXECUTED"] is False
    assert result["MARKET_07_CREATED"] is False
    assert result["NOT_PROVEN_ALPHA"] is True
    assert result["CLASSIFICATION"] in {
        "D7_PROMISING_PROTOTYPE",
        "D7_NO_USEFUL_STRUCTURE",
    }
    (repo / OS.RESULT_JSON_REL).unlink()
    (repo / OS.RESULT_MD_REL).unlink()


def test_freeze_artifact_is_d7_only_and_unexecuted():
    path = REPO / OS.FREEZE_JSON_REL
    if not path.is_file():
        pytest.skip("freeze artifact not written yet")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["STATUS"] == "FROZEN"
    assert payload["SCOPE"] == "D7_ONLY"
    assert payload["D7_EXECUTED"] is False
    assert payload["D7_EXECUTION_AUTHORIZED"] is True
    assert payload["D8_EXECUTION_AUTHORIZED"] is False
    assert payload["D8_EXECUTED"] is False
    assert payload["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert payload["PROTECTED_2025_OPENED"] is False
    assert payload["PROTECTED_2026_OPENED"] is False
    assert payload["MARKET_07_CREATED"] is False
    assert payload["NEXT_UNIT"] == OS.ONE_SHOT_UNIT
    assert payload["D7_SELECTOR_DIGEST"] == I.D7_SELECTOR_DIGEST
    assert not (REPO / OS.RESULT_JSON_REL).exists()
    assert payload["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert "MU_D7_RULE" not in payload
    assert "HEAD" not in payload
    assert "TREE" not in payload
    assert payload.get("CURRENT_PR_HEAD") is None
    assert payload.get("CURRENT_PR_TREE") is None
    assert payload["CURRENT_PR_HEAD_BOUND"] is False


def test_runner_sha256_is_bound_by_permit():
    stored = json.loads((REPO / OS.PERMIT_REL).read_text(encoding="utf-8"))
    runner_sha = OS.current_runner_sha256(REPO)
    assert stored["ONE_SHOT_RUNNER_SHA256"] == runner_sha
    assert "FROZEN_ONE_SHOT_RUNNER_SHA256" not in inspect.getsource(OS)
    source = Path(OS.__file__).read_text(encoding="utf-8")
    assert runner_sha not in source


def test_runner_byte_mutation_fails_before_target(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    runner = repo / OS.RUNNER_REL
    runner.write_text(
        runner.read_text(encoding="utf-8") + "\n# runner-byte-mutation\n",
        encoding="utf-8",
    )
    called = {"target": False, "eval": False}

    def boom_arrays(*_args, **_kwargs):
        called["target"] = True
        raise AssertionError("target constructor ran")

    def boom_eval(*_args, **_kwargs):
        called["eval"] = True
        raise AssertionError("evaluator ran")

    with pytest.raises(OS.OneShotExecutionError, match="RUNNER_SHA256_NE_PERMIT"):
        OS.verify_tracked_permit(repo)
    with patch.object(
        OS, "construct_d7_scientific_arrays", side_effect=boom_arrays
    ), patch.object(OS, "call_reviewed_d7_evaluator", side_effect=boom_eval):
        with pytest.raises(OS.OneShotExecutionError, match="RUNNER_SHA256_NE_PERMIT"):
            OS.execute_one_shot(repo)
    assert called["target"] is False
    assert called["eval"] is False
    assert not (repo / OS.RESULT_JSON_REL).exists()
    assert not (repo / OS.RESULT_MD_REL).exists()


def test_permit_runner_hash_mutation_fails_before_target(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    path = repo / OS.PERMIT_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ONE_SHOT_RUNNER_SHA256"] = "0" * 64
    path.write_text(I.canonical_json(payload), encoding="utf-8")
    called = {"target": False, "eval": False}

    def boom_arrays(*_args, **_kwargs):
        called["target"] = True
        raise AssertionError("target constructor ran")

    def boom_eval(*_args, **_kwargs):
        called["eval"] = True
        raise AssertionError("evaluator ran")

    with pytest.raises(OS.OneShotExecutionError, match="RUNNER_SHA256_NE_PERMIT"):
        OS.verify_pre_scientific_authorities(repo)
    with patch.object(
        OS, "construct_d7_scientific_arrays", side_effect=boom_arrays
    ), patch.object(OS, "call_reviewed_d7_evaluator", side_effect=boom_eval):
        with pytest.raises(OS.OneShotExecutionError, match="RUNNER_SHA256_NE_PERMIT"):
            OS.execute_one_shot(repo)
    assert called["target"] is False
    assert called["eval"] is False
    assert not (repo / OS.RESULT_JSON_REL).exists()


def test_changing_runner_sha_changes_run_identity():
    payload = OS.permit_binding_payload(REPO)
    original = OS.compute_run_identity(payload)
    payload["ONE_SHOT_RUNNER_SHA256"] = "0" * 64
    mutated = OS.compute_run_identity(payload)
    assert original != mutated
    assert len(original) == 64
    assert len(mutated) == 64


def test_execute_one_shot_must_not_write_permit(tmp_path):
    repo = _copy_repo_tree(tmp_path)
    execute_src = inspect.getsource(OS.execute_one_shot)
    assert "write_permit(" not in execute_src
    assert "write_freeze_artifacts(" not in execute_src

    def fake_load(**_kwargs):
        return []

    def fake_hours(_bars):
        return []

    def fake_states(_hours):
        return []

    def fake_reconstruct(states, *, session=None):
        if session is not None:
            session.identity_ok = True
        return {
            "SELECTOR_N": I.D7_SELECTOR_N,
            "SELECTOR_DIGEST": I.D7_SELECTOR_DIGEST,
            "CONSTRUCTED_HOURS": I.D7_CONSTRUCTED_HOURS,
            "VALID_IMPACT_ROWS": I.D7_VALID_IMPACT_ROWS,
            "TARGET_ELIGIBLE_ROWS": I.D7_TARGET_ELIGIBLE_ROWS,
            "SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED": False,
        }

    def fake_arrays(states, *, session=None):
        if session is None or session.identity_ok is not True:
            raise OS.TargetBeforeIdentityError("TARGET_BEFORE_IDENTITY_GATE")
        session.target_constructed = True
        candidate, target, year, buckets, eligible = _gate_arrays(
            candidate_on=True, target_on=True
        )
        return {
            "candidate": candidate,
            "target": target,
            "year": year,
            "rv_bucket": buckets,
            "target_eligible": eligible,
        }

    def boom_write(_repo):
        raise AssertionError("write_permit called during execute_one_shot")

    with patch.object(OS, "write_permit", side_effect=boom_write), patch.object(
        I, "load_legal_1m_bars", side_effect=fake_load
    ), patch.object(I, "aggregate_completed_hours", side_effect=fake_hours), patch.object(
        I, "build_d7_states", side_effect=fake_states
    ), patch.object(
        OS, "reconstruct_d7_selector_identity", side_effect=fake_reconstruct
    ), patch.object(
        OS, "construct_d7_scientific_arrays", side_effect=fake_arrays
    ), patch.object(
        OS, "_git", return_value="deadbeef"
    ):
        result = OS.execute_one_shot(repo)
    assert result["CLASSIFICATION"] in {
        "D7_PROMISING_PROTOTYPE",
        "D7_NO_USEFUL_STRUCTURE",
    }
    (repo / OS.RESULT_JSON_REL).unlink()
    (repo / OS.RESULT_MD_REL).unlink()


def test_freeze_provenance_is_authority_parent_not_current_pr_head():
    path = REPO / OS.FREEZE_JSON_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["PROVENANCE_MODEL"] == OS.PROVENANCE_MODEL
    assert payload["AUTHORITY_PARENT_COMMIT"] == OS.BASE_MAIN_SHA
    assert payload["AUTHORITY_PARENT_COMMIT"] == OS.AUTHORITY_PARENT_COMMIT
    assert payload["AUTHORITY_PARENT_TREE"] == OS.AUTHORITY_PARENT_TREE
    import subprocess

    parent_tree = subprocess.check_output(
        ["git", "rev-parse", f"{OS.AUTHORITY_PARENT_COMMIT}^{{tree}}"],
        cwd=REPO,
        text=True,
    ).strip()
    parent_type = subprocess.check_output(
        ["git", "cat-file", "-t", OS.AUTHORITY_PARENT_COMMIT],
        cwd=REPO,
        text=True,
    ).strip()
    current_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    current_tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=REPO, text=True
    ).strip()
    assert parent_type == "commit"
    assert payload["AUTHORITY_PARENT_TREE"] == parent_tree
    assert payload["AUTHORITY_PARENT_COMMIT"] != current_head
    assert payload["AUTHORITY_PARENT_TREE"] != current_tree
    assert payload["CURRENT_PR_HEAD_BOUND"] is False
    assert "HEAD" not in payload
    assert "TREE" not in payload


def test_permit_binds_live_runner_and_impl_only_as_runtime_executables():
    freeze = json.loads((REPO / OS.FREEZE_JSON_REL).read_text(encoding="utf-8"))
    assert freeze["D7_RUNTIME_EXECUTABLE_DEPENDENCIES"] == [
        OS.RUNNER_REL,
        OS.IMPL_REL,
    ]
    impl_src = Path(I.__file__).read_text(encoding="utf-8")
    assert "import numpy as np" in impl_src
    assert "from scripts" not in impl_src
    assert "import scripts" not in impl_src
    runner_src = inspect.getsource(OS.execute_one_shot)
    assert "discovery_sprint_02_impl" in Path(OS.__file__).read_text(encoding="utf-8")
    assert "discovery_sprint_02_feasibility" not in runner_src
