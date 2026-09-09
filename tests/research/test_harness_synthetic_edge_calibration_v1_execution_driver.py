"""Canonical production execution-driver tests.

Disposable repos and a tiny non-production plan only. These tests must not run
the frozen 3200-world Monte Carlo, mint a live production RESULT, access real
market data, open B2-06, or inspect 2025/2026.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from tests.research.test_harness_synthetic_edge_calibration_v1_production import (
    PRODUCTION_PATH,
    REPO,
    _assert_clean,
    _authority_sha_map,
    _bind_prod,
    _commit_arm_authorizing_parent,
    _commit_driver_freeze,
    _commit_production_tree,
    _driver_freeze_payload,
    _git,
    _live_bytes,
    _mock_record,
    _planned_records,
    _sha,
    _write,
)

FIXTURE_JOBS = (
    ("NULL", 50, 0),
    ("EASY", 50, 0),
    ("MODERATE", 50, 1),
)


@pytest.fixture(autouse=True)
def _isolate_canonical_sessions():
    prod._LIVE_SESSIONS.clear()
    prod._CAPABILITY_KEEPALIVE.clear()
    prod._CLOSED_SESSIONS.clear()
    prod._CLOSED_CAPABILITY_KEEPALIVE.clear()
    yield
    prod._LIVE_SESSIONS.clear()
    prod._CAPABILITY_KEEPALIVE.clear()
    prod._CLOSED_SESSIONS.clear()
    prod._CLOSED_CAPABILITY_KEEPALIVE.clear()


def _fixture_record(scenario_id: str, n_rows: int, world_index: int, **kwargs) -> dict:
    return _mock_record(scenario_id, n_rows, world_index, **kwargs)


def _valid_evaluator(scenario_id: str, n_rows: int, world_index: int) -> dict:
    return _fixture_record(scenario_id, n_rows, world_index)


def _armed_repo(tmp_path: Path, monkeypatch) -> Path:
    repo = _commit_production_tree(tmp_path)
    _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    return repo


def _science_probe(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("scientific evaluation ran before an authority refusal")

    monkeypatch.setattr(prod, "simulate_dgp", boom)
    monkeypatch.setattr(prod, "_evaluate_planned_world_body", boom)
    monkeypatch.setattr(prod, "evaluate_production_candidate", boom)


def test_live_head_remains_unarmed_and_has_no_arm_artifact():
    assert (REPO / prod.CANONICAL_ARM_PATH).exists() is False
    assert (REPO / prod.CANONICAL_RESULT_PATH).exists() is False
    assert prod.production_monte_carlo_arm_authorized() is False
    state = prod.inspect_production_arm_state()
    assert state == {"present": False, "authorized": False}
    identity = prod.production_durability_identity()
    assert identity["production_monte_carlo_arm_authorized"] is False
    assert identity["monte_carlo_armed"] is False
    assert identity["production_result_minted"] is False
    assert identity["authorization_consumed"] is False
    assert identity["stage"] == "production_execution_driver_unarmed"
    assert len(prod.planned_production_jobs()) == 3200


def test_positive_armed_fixture_driver_reaches_result_mint_path(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path, monkeypatch)
    evaluated: list[tuple[str, int, int]] = []

    def evaluator(scenario_id, n_rows, world_index):
        evaluated.append((scenario_id, n_rows, world_index))
        return _valid_evaluator(scenario_id, n_rows, world_index)

    reservation = prod.durable_reservation_document(repo)
    envelope = prod.run_canonical_fixture_driver(FIXTURE_JOBS, evaluator)
    assert evaluated == list(FIXTURE_JOBS)
    assert set(envelope.keys()) == {"core", "core_sha256", "core_size"}
    core = envelope["core"]
    assert core["fixture"] is True
    assert core["not_a_production_result"] is True
    assert core["planned_world_count"] == 3
    assert core["observed_world_count"] == 3
    assert core["run_identity"] == prod.canonical_run_identity(repo)
    assert core["run_identity"] == reservation["run_identity"]
    assert core["mechanical_conclusion"] == "FIXTURE_COMPLETE_NOT_PRODUCTION"
    assert core["real_market_data_access_authorized"] is False
    assert core["b2_06_scientific_execution_authorized"] is False
    assert core["validation_2025_authorized"] is False
    assert core["oos_2026_authorized"] is False
    assert len(core["record_digest_chain"]) == 3
    assert (repo / prod.CANONICAL_RESULT_PATH).exists() is False
    assert prod.production_monte_carlo_arm_authorized(repo) is True


def test_unarmed_production_driver_refuses_before_science(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _science_probe(monkeypatch)
    with pytest.raises(prod.ProductionNotArmed, match="production_monte_carlo_arm_authorized=false"):
        prod.run_canonical_production_execution()
    with pytest.raises(prod.ProductionNotArmed, match="production_monte_carlo_arm_authorized=false"):
        prod.run_canonical_fixture_driver(FIXTURE_JOBS, _valid_evaluator)


def test_direct_mint_final_result_fabricated_records_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="caller-supplied records cannot mint"
    ):
        prod.mint_final_result(_planned_records())
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="caller-supplied records cannot mint"
    ):
        prod.mint_final_result()


def test_fabricated_records_plus_valid_arm_refuse_without_capability(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="caller-supplied records cannot mint"
    ):
        prod.mint_final_result(_planned_records())
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="caller arguments cannot authorize"
    ):
        prod.mint_final_result(_planned_records(), capability=object())


def test_cross_session_capability_refuses(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    cap_a = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    cap_b = prod.open_canonical_fixture_session((("SMALL", 50, 0),), _valid_evaluator)
    try:
        for job in FIXTURE_JOBS:
            prod.evaluate_canonical_session_job(cap_a, *job)
        with pytest.raises(
            lib.SyntheticExecutionNotAuthorized, match="extra world is not in the session plan"
        ):
            prod.evaluate_canonical_session_job(cap_b, *FIXTURE_JOBS[0])
        with pytest.raises(
            lib.SyntheticExecutionNotAuthorized,
            match="INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
        ):
            prod.mint_session_result(cap_b)
        minted = prod.mint_session_result(cap_a)
        assert minted["core"]["not_a_production_result"] is True
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="stale"):
            prod.mint_session_result(cap_a)
    finally:
        for cap in (cap_a, cap_b):
            try:
                prod.abandon_canonical_session(cap)
            except lib.SyntheticExecutionNotAuthorized:
                pass


def test_stale_capability_after_completion_refuses(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    for job in FIXTURE_JOBS:
        prod.evaluate_canonical_session_job(cap, *job)
    envelope = prod.mint_session_result(cap)
    assert envelope["core"]["not_a_production_result"] is True
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="stale"):
        prod.mint_session_result(cap)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="stale"):
        prod.evaluate_canonical_session_job(cap, *FIXTURE_JOBS[0])


def test_caller_cannot_construct_equivalent_capability(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="not valid"):
        prod.mint_session_result(object())
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="not valid"):
        prod.mint_session_result({"capability": "forged", "token": "ab" * 32})
    fake = prod._CanonicalExecutionSession()
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="not valid"):
        prod.mint_session_result(fake)
    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    try:
        with pytest.raises(
            lib.SyntheticExecutionNotAuthorized, match="caller arguments cannot authorize"
        ):
            prod.mint_session_result(cap, records=[_valid_evaluator(*FIXTURE_JOBS[0])])
    finally:
        prod.abandon_canonical_session(cap)


def test_missing_duplicate_extra_and_wrong_seed_refuse(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    try:
        prod.evaluate_canonical_session_job(cap, *FIXTURE_JOBS[0])
        prod.evaluate_canonical_session_job(cap, *FIXTURE_JOBS[1])
        with pytest.raises(
            lib.SyntheticExecutionNotAuthorized,
            match="INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
        ):
            prod.mint_session_result(cap)
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="duplicate world identity"):
            prod.evaluate_canonical_session_job(cap, *FIXTURE_JOBS[0])
        with pytest.raises(
            lib.SyntheticExecutionNotAuthorized, match="extra world is not in the session plan"
        ):
            prod.evaluate_canonical_session_job(cap, "TINY_NOISY", 50, 9)
    finally:
        prod.abandon_canonical_session(cap)

    def wrong_seed(scenario_id, n_rows, world_index):
        rec = _valid_evaluator(scenario_id, n_rows, world_index)
        rec["world_seed"] = int(rec["world_seed"]) + 1
        return rec

    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="world seed does not match frozen plan"
    ):
        prod.run_canonical_fixture_driver(FIXTURE_JOBS, wrong_seed)


def test_invalid_world_remains_in_denominator_and_incomplete_world_forces_conclusion(
    tmp_path, monkeypatch
):
    _armed_repo(tmp_path, monkeypatch)

    def invalid_eval(scenario_id, n_rows, world_index):
        return _fixture_record(
            scenario_id,
            n_rows,
            world_index,
            valid=False,
            invalid_reasons=("bootstrap_invalid",),
        )

    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, invalid_eval)
    try:
        records = [prod.evaluate_canonical_session_job(cap, *job) for job in FIXTURE_JOBS]
        assert all(rec["valid"] is False for rec in records)
        assert all(rec["stays_in_denominator"] is True for rec in records)
        with pytest.raises(
            lib.SyntheticExecutionNotAuthorized,
            match="INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
        ):
            prod.mint_session_result(cap)
        assert len(records) == 3
    finally:
        prod.abandon_canonical_session(cap)

    def incomplete_eval(scenario_id, n_rows, world_index):
        if world_index == 0 and scenario_id == "NULL":
            raise lib.IncompleteWorld("rank deficient fixture world")
        return _valid_evaluator(scenario_id, n_rows, world_index)

    cap2 = prod.open_canonical_fixture_session(FIXTURE_JOBS, incomplete_eval)
    try:
        rec = prod.evaluate_canonical_session_job(cap2, *FIXTURE_JOBS[0])
        assert rec["valid"] is False
        assert rec["stays_in_denominator"] is True
        assert rec["world_identity"] == lib.world_identity(*FIXTURE_JOBS[0])
        prod.evaluate_canonical_session_job(cap2, *FIXTURE_JOBS[1])
        prod.evaluate_canonical_session_job(cap2, *FIXTURE_JOBS[2])
        with pytest.raises(
            lib.SyntheticExecutionNotAuthorized,
            match="INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
        ):
            prod.mint_session_result(cap2)
    finally:
        prod.abandon_canonical_session(cap2)

    production_records = _planned_records()
    production_records[0] = {
        **production_records[0],
        "valid": False,
        "invalid_reasons": ["rank deficient fixture world"],
        "stays_in_denominator": True,
    }
    aggregates = prod.aggregate_planned_worlds(production_records)
    assert aggregates["observed_world_count"] == 3200
    assert aggregates["incomplete_execution"] is True
    assert aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"


def test_crash_before_completion_cannot_mint(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    prod.evaluate_canonical_session_job(cap, *FIXTURE_JOBS[0])
    prod.abandon_canonical_session(cap)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="stale"):
        prod.mint_session_result(cap)


def test_conflicting_second_attempt_follows_115_result_consumed_semantics(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _write(repo / prod.CANONICAL_RESULT_PATH, "{}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "tracked production RESULT already present")
    _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    _science_probe(monkeypatch)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="production RESULT already exists; one-shot authority is consumed",
    ):
        prod.run_canonical_production_execution()


def test_post_result_rerun_reports_one_shot_consumed_not_unarmed(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path, monkeypatch)
    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    for job in FIXTURE_JOBS:
        prod.evaluate_canonical_session_job(cap, *job)
    envelope = prod.mint_session_result(cap)
    raw = prod.canonical_json_bytes(prod._jsonable(envelope))
    _write(repo / prod.CANONICAL_RESULT_PATH, raw.decode("utf-8"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "canonical RESULT descendant")
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    _science_probe(monkeypatch)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="production RESULT already exists; one-shot authority is consumed",
    ):
        prod.run_canonical_production_execution()
    rc = prod.fresh_process_worker_main()
    assert rc == 2
    # Worker prints the one-shot reason on stderr; capture via monkeypatch of print is
    # unnecessary because the same RESULT-first guard is asserted above. Re-run the
    # worker path with stderr capture through the isolated helper:
    import io
    from contextlib import redirect_stderr

    buf = io.StringIO()
    with redirect_stderr(buf):
        rc2 = prod.fresh_process_worker_main()
    assert rc2 == 2
    assert "one-shot authority is consumed" in buf.getvalue()
    assert "production_monte_carlo_arm_authorized=false" not in buf.getvalue()


def test_dirty_worktree_refuses_before_science(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path, monkeypatch)
    _science_probe(monkeypatch)
    _write(repo / "docs/research/DIRTY.txt", "uncommitted\n")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze"):
        prod.run_canonical_fixture_driver(FIXTURE_JOBS, _valid_evaluator)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze"):
        prod.run_canonical_production_execution()


def test_authority_byte_mismatch_refuses_before_science(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path, monkeypatch)
    _science_probe(monkeypatch)
    evil = tmp_path / "evil_production.py"
    evil.write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# executed byte mismatch\n")

    def executing(rel: str) -> Path:
        if rel == prod.PRODUCTION_REL:
            return evil
        return (repo / rel).resolve()

    monkeypatch.setattr(prod, "_executing_file", executing)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="executed bytes differ from HEAD"
    ):
        prod.run_canonical_fixture_driver(FIXTURE_JOBS, _valid_evaluator)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="executed bytes differ from HEAD"
    ):
        prod.run_canonical_production_execution()


def test_fixture_driver_cannot_encode_production_grid_or_n(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="cannot encode the frozen production grid"
    ):
        prod.run_canonical_fixture_driver(prod.planned_production_jobs(), _valid_evaluator)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="cannot encode production N"):
        prod.run_canonical_fixture_driver((("NULL", 5000, 0),), _valid_evaluator)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="cannot encode production N"):
        prod.run_canonical_fixture_driver((("NULL", 2500, 0),), _valid_evaluator)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="cannot encode production N"):
        prod.run_canonical_fixture_driver((("NULL", 10000, 0),), _valid_evaluator)


def test_future_arm_declared_fields_are_machine_checked(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    reviewed_head, reviewed_tree = _commit_driver_freeze(repo)
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    base = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent,
        "authorized_execution_tree": tree,
        "execution_authority_sha256": _authority_sha_map(repo),
        "reviewed_implementation_head": reviewed_head,
        "reviewed_implementation_tree": reviewed_tree,
        "authorized_grid": prod.frozen_production_grid(),
        **prod.ARM_REQUIRED_LITERALS,
    }
    tamper_cases = (
        {"authorized_run_count": 2},
        {"scope": "everything"},
        {"production_only_scope": False},
        {"authorization_consumed": True},
        {"descendant_implementation_change_authorized": True},
        {"real_market_data_access_authorized": True},
        {"other_hypothesis_authorized": True},
        {"B2_06_scientific_execution_authorized": True},
        {"validation_2025_authorized": True},
        {"oos_2026_authorized": True},
        {"authorized_grid": {**prod.frozen_production_grid(), "root_seed": 1}},
    )
    for override in tamper_cases:
        payload = dict(base)
        payload.update(override)
        _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "tampered ARM field")
        _bind_prod(monkeypatch, repo)
        assert prod.production_monte_carlo_arm_authorized(repo) is False
        state = prod.inspect_production_arm_state(repo)
        assert state["present"] is True
        assert state["authorized"] is False
        _git(repo, "reset", "--hard", "HEAD^")


def test_identity_arm_state_is_dynamic(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    absent = prod.inspect_production_arm_state(repo)
    assert absent == {"present": False, "authorized": False}
    identity = prod.production_durability_identity()
    assert identity["production_monte_carlo_arm_authorized"] is False
    assert identity["monte_carlo_armed"] is False
    assert identity["stage"] == "production_execution_driver_unarmed"

    _commit_arm_authorizing_parent(repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    armed_identity = prod.production_durability_identity()
    assert armed_identity["production_monte_carlo_arm_authorized"] is True
    assert armed_identity["monte_carlo_armed"] is True
    assert armed_identity["stage"] == "production_monte_carlo_arm_authorized"
    assert armed_identity["production_result_minted"] is False
    assert armed_identity["authorization_consumed"] is False

    _write(repo / prod.CANONICAL_ARM_PATH, "{not-json\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "malformed ARM")
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="cannot be verified"):
        prod.inspect_production_arm_state(repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="cannot be verified"):
        prod.production_durability_identity()


def test_altered_production_cannot_arm_by_rewriting_reviewed_fields(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    reviewed_head = _git(repo, "rev-parse", "HEAD")
    reviewed_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    original_sha = _sha(_live_bytes(PRODUCTION_PATH))
    (repo / PRODUCTION_PATH).write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# altered driver\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "alter production.py")
    parent = _git(repo, "rev-parse", "HEAD")
    parent_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    grid = prod.frozen_production_grid()
    literals = dict(prod.ARM_REQUIRED_LITERALS)

    def arm_and_check(payload: dict, message: str) -> None:
        _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", message)
        _bind_prod(monkeypatch, repo)
        assert prod.production_monte_carlo_arm_authorized(repo) is False
        _git(repo, "reset", "--hard", "HEAD^")

    # Keep the original reviewed identity while updating parent digests.
    arm_and_check(
        {
            "production_monte_carlo_arm_authorized": True,
            "authorized_execution_commit": parent,
            "authorized_execution_tree": parent_tree,
            "execution_authority_sha256": _authority_sha_map(repo),
            "reviewed_implementation_head": reviewed_head,
            "reviewed_implementation_tree": reviewed_tree,
            "authorized_grid": grid,
            **literals,
        },
        "ARM with original reviewed identity and updated parent digests",
    )
    # Rewrite reviewed_* onto the altered parent but keep the original production SHA.
    arm_and_check(
        {
            "production_monte_carlo_arm_authorized": True,
            "authorized_execution_commit": parent,
            "authorized_execution_tree": parent_tree,
            "execution_authority_sha256": {
                **_authority_sha_map(repo),
                "production": original_sha,
            },
            "reviewed_implementation_head": parent,
            "reviewed_implementation_tree": parent_tree,
            "authorized_grid": grid,
            **literals,
        },
        "rewrite reviewed fields but keep original production SHA",
    )
    # Rewrite reviewed_* to a commit that is not an ancestor of the parent.
    arm_and_check(
        {
            "production_monte_carlo_arm_authorized": True,
            "authorized_execution_commit": parent,
            "authorized_execution_tree": parent_tree,
            "execution_authority_sha256": _authority_sha_map(repo),
            "reviewed_implementation_head": "ab" * 20,
            "reviewed_implementation_tree": "cd" * 20,
            "authorized_grid": grid,
            **literals,
        },
        "rewrite reviewed fields to a non-ancestor",
    )


def test_no_reroll_and_planned_3200_remain_authoritative():
    jobs = prod.planned_production_jobs()
    assert len(jobs) == 3200
    assert len(set(jobs)) == 3200
    source = Path(prod.__file__).read_text(encoding="utf-8")
    assert "run_canonical_production_execution" in source
    assert "production world plan is not 3200 identities" in source
    assert "caller-supplied records cannot mint a production RESULT" in source
    assert "automatic_retry_authorized" in source
    assert source.count("automatic_retry_authorized") >= 1
    assert prod.WORKER_STDOUT_KIND_COMPLETE_RESULT == "COMPLETE_RESULT"
    assert prod.WORKER_STDOUT_KIND_PARTIAL == "PARTIAL_NOT_RESULT"
    assert (REPO / prod.CANONICAL_DRIVER_FREEZE_PATH).exists() is False


def _live_session(capability: object):
    session = prod._LIVE_SESSIONS.get(id(capability))
    assert session is not None
    return session


def _emit_capture(monkeypatch):
    captured: dict[str, object] = {}

    def emit(kind, payload):
        raw = prod.canonical_worker_stdout_bytes(kind, payload)
        captured["kind"] = kind
        captured["payload"] = payload
        captured["raw"] = raw
        return raw

    monkeypatch.setattr(prod, "_emit_canonical_worker_stdout", emit)
    return captured


def test_fixture_session_result_roundtrips_through_verifier(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    records = [prod.evaluate_canonical_session_job(cap, *job) for job in FIXTURE_JOBS]
    envelope = prod.mint_session_result(cap)
    raw = prod.canonical_json_bytes(envelope)
    parsed = json.loads(raw.decode("utf-8"))
    prod.verify_bound_result_document(parsed, records)
    assert parsed["core"]["fixture"] is True
    for field, value in (
        ("mechanical_conclusion", "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK"),
        ("production_monte_carlo_arm_authorized", False),
        ("run_identity", "ab" * 32),
    ):
        core = dict(parsed["core"])
        core[field] = value
        tamper_bytes = prod.canonical_json_bytes(prod._jsonable(core))
        tamper = {
            "core": core,
            "core_sha256": _sha(tamper_bytes),
            "core_size": len(tamper_bytes),
        }
        with pytest.raises(prod.ProductionIntegrityError, match="core payload tamper|run_identity tamper"):
            prod.verify_bound_result_document(tamper, records)
    mutated = [dict(rec) for rec in records]
    mutated[0] = dict(mutated[0])
    mutated[0]["taxonomy"] = "TRUE_DISCOVERY"
    with pytest.raises(prod.ProductionIntegrityError, match="core payload tamper|world_set"):
        prod.verify_bound_result_document(parsed, mutated)


def test_worker_emits_complete_result_canonical_bytes(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path, monkeypatch)
    envelope = prod.run_canonical_fixture_driver(FIXTURE_JOBS, _valid_evaluator)
    monkeypatch.setattr(prod, "run_canonical_production_execution", lambda: envelope)
    captured = _emit_capture(monkeypatch)
    rc = prod.fresh_process_worker_main()
    assert rc == 0
    expected = prod.canonical_worker_stdout_bytes(
        prod.WORKER_STDOUT_KIND_COMPLETE_RESULT, envelope
    )
    assert captured["raw"] == expected
    parsed = json.loads(captured["raw"].decode("utf-8"))
    assert parsed["kind"] == prod.WORKER_STDOUT_KIND_COMPLETE_RESULT
    assert parsed["final_result_minted"] is True
    assert parsed["kind"] != prod.WORKER_STDOUT_KIND_PARTIAL
    assert parsed["payload"] == envelope
    assert (repo / prod.CANONICAL_RESULT_PATH).exists() is False


def test_worker_emits_distinguishable_partial_payload(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path, monkeypatch)
    partial = prod.persist_partial_worlds([_valid_evaluator(*FIXTURE_JOBS[0])])
    assert partial["final_result_minted"] is False
    assert partial["status"] == "PARTIAL_NOT_RESULT"

    def boom():
        exc = RuntimeError("canonical crash")
        exc._canonical_partial = partial
        raise exc

    monkeypatch.setattr(prod, "run_canonical_production_execution", boom)
    captured = _emit_capture(monkeypatch)
    rc = prod.fresh_process_worker_main()
    assert rc == 2
    expected = prod.canonical_worker_stdout_bytes(prod.WORKER_STDOUT_KIND_PARTIAL, partial)
    assert captured["raw"] == expected
    parsed = json.loads(captured["raw"].decode("utf-8"))
    assert parsed["kind"] == prod.WORKER_STDOUT_KIND_PARTIAL
    assert parsed["final_result_minted"] is False
    assert parsed["kind"] != prod.WORKER_STDOUT_KIND_COMPLETE_RESULT
    assert parsed["payload"]["status"] == "PARTIAL_NOT_RESULT"


def test_spawn_capture_unarmed_has_no_result_payload(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    capture = prod.spawn_canonical_production_process()
    assert capture == 2
    assert isinstance(capture, prod.CanonicalWorkerCapture)
    assert isinstance(capture.stdout_bytes, bytes)
    assert prod.WORKER_STDOUT_KIND_COMPLETE_RESULT.encode("ascii") not in capture.stdout_bytes
    assert b"core_sha256" not in capture.stdout_bytes
    assert "production_monte_carlo_arm_authorized=false" in capture.stderr


def test_self_reviewed_parent_arm_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent,
        "authorized_execution_tree": tree,
        "execution_authority_sha256": _authority_sha_map(repo),
        "reviewed_implementation_head": parent,
        "reviewed_implementation_tree": tree,
        "authorized_grid": prod.frozen_production_grid(),
        **prod.ARM_REQUIRED_LITERALS,
    }
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "self-bless ARM without freeze")
    _bind_prod(monkeypatch, repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False


def test_modified_parent_consistent_arm_and_freeze_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _commit_driver_freeze(repo)
    (repo / PRODUCTION_PATH).write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# altered driver\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "modify production.py after freeze")
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze = _driver_freeze_payload(repo, parent, tree)
    _write(
        repo / prod.CANONICAL_DRIVER_FREEZE_PATH,
        json.dumps(freeze, indent=2, sort_keys=True) + "\n",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "rewrite freeze onto modified parent")
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent,
        "authorized_execution_tree": tree,
        "execution_authority_sha256": _authority_sha_map(repo),
        "reviewed_implementation_head": parent,
        "reviewed_implementation_tree": tree,
        "authorized_grid": prod.frozen_production_grid(),
        **prod.ARM_REQUIRED_LITERALS,
    }
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "consistent ARM of modified self-reviewed parent")
    _bind_prod(monkeypatch, repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False


def test_record_content_substitution_and_cross_session_swap_refuse(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)
    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    for job in FIXTURE_JOBS:
        prod.evaluate_canonical_session_job(cap, *job)
    session = _live_session(cap)
    genuine = prod._jsonable(dict(session.records[0]))
    fake = dict(genuine)
    fake["taxonomy"] = "TRUE_DISCOVERY"
    fake["taxonomy_flags"] = {**genuine["taxonomy_flags"], "TRUE_DISCOVERY": True}
    session.records = (prod._immutable_record(fake),) + tuple(session.records[1:])
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="record content digest chain mismatch"
    ):
        prod.mint_session_result(cap)

    cap_valid = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    for job in FIXTURE_JOBS:
        prod.evaluate_canonical_session_job(cap_valid, *job)
    session = _live_session(cap_valid)
    flipped = prod._jsonable(dict(session.records[1]))
    flipped["valid"] = False
    fake_reason = dict(flipped)
    fake_reason["invalid_reasons"] = ["fabricated"]
    session.records = (session.records[0], prod._immutable_record(fake_reason)) + tuple(
        session.records[2:]
    )
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="record content digest chain mismatch"
    ):
        prod.mint_session_result(cap_valid)

    cap_metric = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    for job in FIXTURE_JOBS:
        prod.evaluate_canonical_session_job(cap_metric, *job)
    session = _live_session(cap_metric)
    metric = prod._jsonable(dict(session.records[2]))
    metric["oracle_F03"] = {
        **metric.get("oracle_F03", {}),
        "gates": {"MODEL_DETECTED": True, "STRICT_PASS": True},
    }
    session.records = tuple(session.records[:2]) + (prod._immutable_record(metric),)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="record content digest chain mismatch"
    ):
        prod.mint_session_result(cap_metric)

    cap_a = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    cap_b = prod.open_canonical_fixture_session(
        (("SMALL", 50, 0), ("TINY_NOISY", 50, 0), ("NULL", 50, 1)),
        _valid_evaluator,
    )
    for job in FIXTURE_JOBS:
        prod.evaluate_canonical_session_job(cap_a, *job)
    for job in (("SMALL", 50, 0), ("TINY_NOISY", 50, 0), ("NULL", 50, 1)):
        prod.evaluate_canonical_session_job(cap_b, *job)
    session_a = _live_session(cap_a)
    session_b = _live_session(cap_b)
    session_a.records = (session_b.records[0],) + tuple(session_a.records[1:])
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="record content digest chain mismatch|does not match planned job",
    ):
        prod.mint_session_result(cap_a)
    prod.abandon_canonical_session(cap_b)

    cap_mix = prod.open_canonical_fixture_session(FIXTURE_JOBS, _valid_evaluator)
    for job in FIXTURE_JOBS:
        prod.evaluate_canonical_session_job(cap_mix, *job)
    session = _live_session(cap_mix)
    fabricated = _valid_evaluator(*FIXTURE_JOBS[2])
    fabricated["taxonomy"] = "FALSE_DISCOVERY"
    session.records = tuple(session.records[:2]) + (prod._immutable_record(fabricated),)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="record content digest chain mismatch"
    ):
        prod.mint_session_result(cap_mix)


def test_abort_paths_retire_session_and_refuse_mint(tmp_path, monkeypatch):
    _armed_repo(tmp_path, monkeypatch)

    def _assert_retired(exc_type, factory):
        cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, factory)
        assert id(cap) in prod._LIVE_SESSIONS
        with pytest.raises(exc_type):
            prod.evaluate_canonical_session_job(cap, *FIXTURE_JOBS[0])
        assert id(cap) not in prod._LIVE_SESSIONS
        assert len(prod._LIVE_SESSIONS) == 0
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="stale|not valid"):
            prod.mint_session_result(cap)

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt()

    def sys_exit(*args, **kwargs):
        raise SystemExit(9)

    def generic(*args, **kwargs):
        raise RuntimeError("evaluator failed")

    _assert_retired(KeyboardInterrupt, interrupt)
    assert not prod._LIVE_SESSIONS
    _assert_retired(SystemExit, sys_exit)
    assert not prod._LIVE_SESSIONS
    _assert_retired(RuntimeError, generic)
    assert not prod._LIVE_SESSIONS
