"""BLOCKER-2: self-consistent checkpoint content is not scientific authority.

Resume may retain structurally valid cached worlds as UNTRUSTED pending
verification. Authoritative authentication recomputes each cached record
from exact frozen git execution bytes in an isolated child. A forged
record that preserves identity/schema and honest SHA256 digests MUST be
refused. Secrets/HMAC are not used.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    SyntheticExecutionNotAuthorized,
    world_identity,
    world_seed,
)
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from tests.research.test_harness_synthetic_edge_calibration_v1_tcb_durability import (
    JOBS,
    ONE,
    _bind_prod,
    _cheap_world,
    _commit_production_tree,
    _mock_record,
    _store,
)

pytestmark = pytest.mark.research

TWO = JOBS[:2]


@pytest.fixture(autouse=True)
def _reset_durability_hook():
    prod._TEST_DURABILITY_HOOK = None
    yield
    prod._TEST_DURABILITY_HOOK = None


def _copy(rec):
    return json.loads(json.dumps(rec))


def _legit_records(tmp_path, repo, jobs=ONE):
    store = _store(tmp_path, repo, jobs=jobs)
    records = prod.evaluate_planned_jobs_fail_closed(
        jobs, durable_partial=store
    )
    return store, records


def _authenticate(records, jobs, repo):
    return prod.authenticate_cached_world_records_from_frozen_execution(
        planned=jobs,
        records=records,
        repo_root=repo,
        production=False,
    )


def _mutate_candidate_metric(rec):
    rec["oracle_F03"]["MEAN_AE_IMPROVEMENT"] = float(
        rec["oracle_F03"]["MEAN_AE_IMPROVEMENT"]
    ) + 0.01
    return rec


def _mutate_placebo_q95(rec):
    rec["oracle_F03"]["placebo"]["placebo_q95"] = float(
        rec["oracle_F03"]["placebo"]["placebo_q95"]
    ) + 0.01
    return rec


def _mutate_bootstrap(rec):
    rec["oracle_F03"]["bootstrap"]["bootstrap_q025"] = float(
        rec["oracle_F03"]["bootstrap"]["bootstrap_q025"]
    ) - 0.01
    return rec


def _mutate_visibility(rec):
    rec["visibility"]["GROUND_TRUTH_VISIBLE"] = not rec["visibility"][
        "GROUND_TRUTH_VISIBLE"
    ]
    return rec


def _mutate_valid_flag(rec):
    rec["valid"] = not rec["valid"]
    return rec


def _mutate_taxonomy(rec):
    rec["taxonomy"] = "FORGED_TAXONOMY"
    return rec


def _mutate_verdict_selection(rec):
    rec["selected_STRICT_PASS"] = (
        "NO_CANDIDATE" if rec["selected_STRICT_PASS"] != "NO_CANDIDATE" else "F03"
    )
    return rec


def test_durability_identity_denies_direct_checkpoint_trust():
    ident = prod.production_durability_identity()
    assert ident["durable_partial_is_not_scientific_authority"] is True
    assert ident["checkpoint_content_trusted_directly"] is False
    assert ident["durable_partial_is_not_result"] is True
    assert ident["durable_partial_is_not_world_records"] is True


def test_authenticate_parent_does_not_call_current_evaluator():
    src = Path(
        "scripts/research/harness_synthetic_edge_calibration_v1_production.py"
    ).read_text(encoding="utf-8")
    start = src.index("def authenticate_cached_world_records_from_frozen_execution")
    end = src.index("\ndef _parse_authenticate_cached_records_proof")
    body = src[start:end]
    assert "_evaluate_planned_world_body(" not in body
    assert "ISOLATED_CHILD_BOOTSTRAP" in body or "_spawn_isolated_child" in body
    assert "hmac" not in body.lower()
    child = src[
        src.index("def authenticate_cached_records_worker_main") : src.index(
            "\ndef _job_from_record"
        )
    ]
    assert "_evaluate_planned_world_body(" in child
    assert "ISOLATED_FROZEN_GIT_EXECUTION" in child


def test_load_structurally_valid_does_not_mean_scientifically_verified(
    tmp_path, monkeypatch
):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    store = _store(tmp_path, repo, jobs=ONE)
    rec = _mock_record(*ONE[0])
    store.checkpoint_completed_world(rec, ONE[0])
    loaded = store.load_structurally_valid_cached()
    assert len(loaded) == 1
    owned = loaded[ONE[0]]
    dumped = json.dumps(owned)
    assert "CHECKPOINT_SCIENTIFICALLY_VERIFIED" not in dumped
    assert owned["world_identity"] == rec["world_identity"]
    wrapper = json.loads(next(store.worlds_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert wrapper.get("trust_state") is None
    assert wrapper.get("scientifically_verified") is not True
    assert store.load_verified_completed() == loaded


def test_resume_retains_structurally_valid_cache_without_immediate_recompute(
    tmp_path, monkeypatch
):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    store = _store(tmp_path, repo, jobs=TWO)
    calls = []

    def tracking(scenario_id, n_rows, world_index):
        calls.append((scenario_id, n_rows, world_index))
        return _cheap_world(scenario_id, n_rows, world_index)

    monkeypatch.setattr(prod, "_evaluate_planned_world_body", tracking)
    prod.evaluate_planned_jobs_fail_closed(ONE, durable_partial=store)
    assert calls == [ONE[0]]
    resumed = prod.evaluate_planned_jobs_fail_closed(TWO, durable_partial=store)
    assert calls == [ONE[0], TWO[1]]
    assert [(r["scenario_id"], r["n_rows"], r["world_index"]) for r in resumed] == list(
        TWO
    )


@pytest.mark.parametrize(
    "mutator",
    [
        _mutate_candidate_metric,
        _mutate_placebo_q95,
        _mutate_bootstrap,
        _mutate_visibility,
        _mutate_valid_flag,
        _mutate_taxonomy,
        _mutate_verdict_selection,
    ],
    ids=[
        "candidate_metric",
        "placebo_q95",
        "bootstrap_field",
        "visibility",
        "valid_flag",
        "failure_taxonomy",
        "verdict_relevant_field",
    ],
)
def test_self_consistent_record_forgery_refused(tmp_path, monkeypatch, mutator):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _, records = _legit_records(tmp_path, repo, jobs=ONE)
    forged = mutator(_copy(records[0]))
    forged_store = _store(tmp_path / "forged", repo, jobs=ONE)
    forged_store.checkpoint_completed_world(forged, ONE[0])
    loaded = forged_store.load_structurally_valid_cached()
    assert loaded, "self-consistent forged bytes must still parse structurally"
    wrapper = json.loads(
        next(forged_store.worlds_dir.glob("*.json")).read_text(encoding="utf-8")
    )
    assert wrapper["record_sha256"] == prod._record_content_digest(wrapper["record"])
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="cached world records do not match frozen execution",
    ):
        _authenticate(list(loaded.values()), ONE, repo)


def test_whole_checkpoint_forgery_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    store = _store(tmp_path, repo, jobs=TWO)
    fabricated = []
    for job in TWO:
        rec = _mock_record(*job)
        rec["valid"] = True
        rec["taxonomy"] = "TRUE_DISCOVERY"
        rec["taxonomy_flags"] = {
            "TRUE_DISCOVERY": True,
            "ANY_EDGE_DECLARED": True,
            "USEFUL_DISCOVERY": True,
        }
        store.checkpoint_completed_world(rec, job)
        fabricated.append(rec)
    loaded = store.load_structurally_valid_cached()
    assert len(loaded) == 2
    for payload_path in store.worlds_dir.glob("*.json"):
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        assert payload["record_sha256"] == prod._record_content_digest(payload["record"])
        assert payload["kind"] == prod.DURABLE_PARTIAL_RECORD_KIND
        assert payload["execution_head"] == store.identity["execution_head"]
        assert payload["plan_sha256"] == store.identity["plan_sha256"]
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="cached world records do not match frozen execution",
    ):
        _authenticate(list(loaded.values()), TWO, repo)


def test_mixed_legitimate_and_forged_checkpoint_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    store, records = _legit_records(tmp_path, repo, jobs=TWO)
    mixed = _store(tmp_path / "mixed", repo, jobs=TWO)
    mixed.checkpoint_completed_world(records[0], TWO[0])
    forged = _mutate_candidate_metric(_copy(records[1]))
    mixed.checkpoint_completed_world(forged, TWO[1])
    loaded = mixed.load_structurally_valid_cached()
    assert len(loaded) == 2
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="cached world records do not match frozen execution",
    ):
        _authenticate(list(loaded.values()), TWO, repo)


def test_forged_digest_and_metadata_recompute_still_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _orig, records = _legit_records(tmp_path, repo, jobs=ONE)
    forged = _mutate_candidate_metric(_copy(records[0]))
    store = _store(tmp_path / "digest", repo, jobs=ONE)
    store.checkpoint_completed_world(forged, ONE[0])
    payload = json.loads(next(store.worlds_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert payload["record_sha256"] == prod._record_content_digest(payload["record"])
    assert payload["record_size"] == len(prod.canonical_json_bytes(payload["record"]))
    assert payload["schema_version"] == 1
    assert payload["run_identity"] == store.identity["run_identity"]
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="cached world records do not match frozen execution",
    ):
        _authenticate(list(store.load_structurally_valid_cached().values()), ONE, repo)


def test_checkpoint_scientifically_verified_metadata_is_not_trusted(
    tmp_path, monkeypatch
):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    original = prod._untrusted_cached_records_payload

    def poisoned(**kwargs):
        payload = original(**kwargs)
        payload["trust_state"] = prod.CHECKPOINT_SCIENTIFICALLY_VERIFIED
        return payload

    monkeypatch.setattr(prod, "_untrusted_cached_records_payload", poisoned)
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="must not self-attest scientific verification",
    ):
        _authenticate([_mock_record(*ONE[0])], ONE, repo)


def test_current_module_monkeypatch_cannot_self_attest_forged_record(
    tmp_path, monkeypatch
):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    forged = [_mock_record(*ONE[0])]

    def liar(scenario_id, n_rows, world_index):
        rec = _copy(forged[0])
        rec["scenario_id"] = scenario_id
        rec["n_rows"] = n_rows
        rec["world_index"] = world_index
        rec["world_identity"] = world_identity(scenario_id, n_rows, world_index)
        rec["world_seed"] = int(world_seed(rec["world_identity"]))
        return rec

    monkeypatch.setattr(prod, "_evaluate_planned_world_body", liar)
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="cached world records do not match frozen execution",
    ):
        _authenticate(forged, ONE, repo)


def test_finalization_without_scientific_verification_refused_by_source_contract():
    src = Path(
        "scripts/research/harness_synthetic_edge_calibration_v1_production.py"
    ).read_text(encoding="utf-8")
    start = src.index("def _mint_from_session(")
    end = src.index("\ndef _attach_partial_payload(")
    body = src[start:end]
    assert body.count("authenticate_cached_world_records_from_frozen_execution") == 1
    assert "if session.production:" in body
    production_branch = body[
        body.index("if session.production:") : body.index(
            'return {"result": envelope, "world_records": world_records}'
        )
    ]
    assert "production=True" in production_branch
    fixture_branch = body[body.rindex("core = _bind_result_core(") :]
    assert "authenticate_cached_world_records_from_frozen_execution" not in fixture_branch
    assert "fixture=True" in fixture_branch


def test_production_authentication_rejects_fixture_plan(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="frozen 3200-world plan",
    ):
        prod.authenticate_cached_world_records_from_frozen_execution(
            planned=ONE,
            records=[_mock_record(*ONE[0])],
            repo_root=repo,
            production=True,
        )


def test_legitimate_interrupted_resumed_then_authenticated(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    store = _store(tmp_path, repo, jobs=TWO)
    prod._TEST_DURABILITY_HOOK = {"interrupt_after": 1}
    with pytest.raises(RuntimeError, match="interrupt after checkpoint"):
        prod.evaluate_planned_jobs_fail_closed(TWO, durable_partial=store)
    prod._TEST_DURABILITY_HOOK = None
    assert len(store.load_structurally_valid_cached()) == 1
    resumed = prod.evaluate_planned_jobs_fail_closed(TWO, durable_partial=store)
    fresh = prod.evaluate_planned_jobs_fail_closed(TWO)
    proof = _authenticate(resumed, TWO, repo)
    assert proof["kind"] == prod.AUTHENTICATE_CACHED_RECORDS_PROOF_KIND
    assert proof["verification_authority"] == "ISOLATED_FROZEN_GIT_EXECUTION"
    assert proof["trust_state"] == prod.CHECKPOINT_SCIENTIFICALLY_VERIFIED
    assert proof["observed_world_count"] == 2
    assert json.dumps(resumed, sort_keys=True) == json.dumps(fresh, sort_keys=True)
    assert prod.CHECKPOINT_CACHED == "CHECKPOINT_CACHED"
    assert prod.CHECKPOINT_STRUCTURALLY_VALID == "CHECKPOINT_STRUCTURALLY_VALID"
