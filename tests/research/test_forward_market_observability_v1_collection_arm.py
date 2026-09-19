"""FORWARD_MARKET_OBSERVABILITY_V1 collection-ARM lifecycle + red-team tests.

Proves, using ONLY fixture data in isolated temp repositories, that the
SAME frozen collector bytes transition UNAUTHORIZED -> AUTHORIZED through
an external, authenticated collection ARM, with no source modification,
and that every forgery/mutation class is refused.

No real collection ARM is created against the live repository. No
scientific/predictive field is computed anywhere in this file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.research.forward_market_observability_v1 import authority_root as root
from scripts.research.forward_market_observability_v1 import collection_authority as auth
from scripts.research.forward_market_observability_v1 import cli as fwd_cli
from scripts.research.forward_market_observability_v1.sources import default_config

REPO = Path(__file__).resolve().parents[2]

AUTH_FILES = tuple(sorted(auth.COLLECTOR_IMPLEMENTATION_HASHES))
ROOT_FILES = (auth.COLLECTION_AUTHORITY_REL, auth.AUTHORITY_ROOT_REL)
DOC_FILES = (auth.REFREEZE_JSON_REL,)


def _bind(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    monkeypatch.setattr(root, "_repo_root", lambda: repo)


def _git(repo: Path, *argv: str) -> None:
    subprocess.run(["git", *argv], cwd=str(repo), check=True, capture_output=True, text=True)


def _fixture_repo(tmp_path: Path) -> Path:
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
    frozen = json.loads((REPO / auth.REFREEZE_JSON_REL).read_text(encoding="utf-8"))[
        root.COLLECTOR_SOURCE_HEAD_KEY
    ]
    _git(repo, "fetch", "--no-tags", "-q", str(REPO), frozen)
    return repo


def _valid_arm_payload() -> dict:
    provenance = auth.collector_source_provenance()
    return {
        "program_id": auth.PROGRAM_ID,
        "collector_source_head": provenance["head"],
        "collector_source_tree": provenance["tree"],
        "collector_implementation_sha_set": dict(auth.COLLECTOR_IMPLEMENTATION_HASHES),
        "raw_envelope_schema": auth.RAW_ENVELOPE_SCHEMA,
        "chunk_schema": auth.CHUNK_SCHEMA,
        "manifest_schema": auth.MANIFEST_SCHEMA,
        "config_schema": auth.CONFIG_SCHEMA,
        "instrument": auth.INSTRUMENT,
        "market_type": auth.MARKET_TYPE,
        "venue": auth.VENUE,
        "sources": auth.source_definitions(),
        "legal_available_at_rule": auth.LEGAL_AVAILABLE_AT_RULE,
        "scientific_outcomes_forbidden": True,
        "market_06_created": False,
        "m04_fwd_created": False,
        "collection_run_identity": auth.derive_collection_run_identity(),
        "authoritative_collection_authorized": True,
    }


def _install_arm(repo: Path, payload: dict | None = None) -> None:
    payload = _valid_arm_payload() if payload is None else payload
    (repo / auth.ARM_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / auth.ARM_JSON_REL).write_bytes(auth.canonical_json_bytes(payload))
    (repo / auth.ARM_MD_REL).write_text("# fixture collection ARM\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "arm")


def _armed_repo(tmp_path: Path) -> Path:
    repo = _fixture_repo(tmp_path)
    _install_arm(repo)
    return repo


# =============================================================================
# 1. Before ARM, "collect" refuses.
# =============================================================================


def test_live_repo_collect_refuses_before_arm():
    assert auth.collection_is_authorized() is False
    with pytest.raises((auth.CollectionNotAuthorized, auth.CollectionAuthorityError)):
        auth.authenticate_collection_arm()


def test_cli_collect_refuses_authoritative_start():
    assert fwd_cli.main(["collect"]) == 2


def test_no_real_collection_arm_exists():
    assert not (REPO / auth.ARM_JSON_REL).exists()
    assert not (REPO / auth.ARM_MD_REL).exists()


# =============================================================================
# 2. After a valid ARM, the SAME source bytes authorize collect.
# =============================================================================


def test_valid_arm_authorizes_the_same_frozen_bytes(tmp_path, monkeypatch):
    before = {rel: (REPO / rel).read_bytes() for rel in AUTH_FILES}
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)

    assert auth.collection_is_authorized() is True
    bound = auth.authenticate_collection_arm()
    assert bound["collection_run_identity"] == auth.derive_collection_run_identity()

    after = {rel: (REPO / rel).read_bytes() for rel in AUTH_FILES}
    assert before == after, "collector source bytes must be unchanged by ARM creation"


def test_run_identity_is_deterministic_and_clock_free():
    first = auth.derive_collection_run_identity()
    second = auth.derive_collection_run_identity()
    assert first == second
    payload = auth.collection_run_identity_payload()
    # "separately_timestamped" is a static source-definition field name
    # (declares a property of a source, not a clock value) and is exempt.
    blob = json.dumps(payload).lower().replace("separately_timestamped", "")
    for forbidden in ("uuid", "generated_at", "created_at", "timestamp", "utcnow"):
        assert forbidden not in blob


# =============================================================================
# 3. Source mutation after ARM refuses.
# =============================================================================


@pytest.mark.parametrize(
    "rel",
    [
        "scripts/research/forward_market_observability_v1/collector.py",
        "scripts/research/forward_market_observability_v1/cli.py",
        "scripts/research/forward_market_observability_v1/sources.py",
        "scripts/research/forward_market_observability_v1/schemas.py",
    ],
)
def test_scientific_file_mutation_after_arm_refused(tmp_path, monkeypatch, rel):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    assert auth.collection_is_authorized() is True
    target = repo / rel
    target.write_text(target.read_text(encoding="utf-8") + "\n# mutated\n", encoding="utf-8")
    with pytest.raises((root.ForwardObservabilityAuthorityRootError, auth.CollectionAuthorityError)):
        auth.authenticate_collection_arm()
    assert auth.collection_is_authorized() is False


def test_collection_authority_module_mutation_after_arm_refused(tmp_path, monkeypatch):
    """The collection-authority module cannot vouch for itself; the root does."""
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    assert auth.collection_is_authorized() is True
    target = repo / auth.COLLECTION_AUTHORITY_REL
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            'if payload.get("authoritative_collection_authorized") is not True:',
            "if False:",
        ),
        encoding="utf-8",
    )
    with pytest.raises(root.ForwardObservabilityAuthorityRootError, match="BLOB_MISMATCH"):
        root.verify_frozen_blob_ids()
    assert auth.collection_is_authorized() is False


# =============================================================================
# 4. Changing config/source definitions after ARM refuses.
# =============================================================================


def test_source_definition_change_after_arm_refused(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    target = repo / "scripts/research/forward_market_observability_v1/sources.py"
    text = target.read_text(encoding="utf-8")
    mutated = text.replace(
        '"poll_interval_seconds": 5,', '"poll_interval_seconds": 999,', 1
    )
    assert mutated != text
    target.write_text(mutated, encoding="utf-8")
    with pytest.raises((root.ForwardObservabilityAuthorityRootError, auth.CollectionAuthorityError)):
        auth.authenticate_collection_arm()


def test_arm_with_wrong_source_definitions_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    payload = _valid_arm_payload()
    sources = [dict(item) for item in payload["sources"]]
    sources[0]["endpoint"] = "wss://attacker.example/ws"
    payload["sources"] = sources
    _install_arm(repo, payload)
    _bind(monkeypatch, repo)
    with pytest.raises(auth.CollectionAuthorityError, match="SOURCE_DEFINITIONS_MISMATCH"):
        auth.authenticate_collection_arm()


# =============================================================================
# 5. Malformed ARM refuses.
# =============================================================================


def test_malformed_arm_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    (repo / auth.ARM_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / auth.ARM_JSON_REL).write_text("{ not json", encoding="utf-8")
    (repo / auth.ARM_MD_REL).write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "malformed")
    _bind(monkeypatch, repo)
    with pytest.raises(auth.CollectionAuthorityError, match="MALFORMED_JSON"):
        auth.authenticate_collection_arm()


def test_arm_with_scientific_field_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    payload = _valid_arm_payload()
    payload["beta"] = 0.1
    _install_arm(repo, payload)
    _bind(monkeypatch, repo)
    with pytest.raises(auth.CollectionAuthorityError, match="SCIENTIFIC_FIELD"):
        auth.authenticate_collection_arm()


def test_untracked_arm_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    payload = _valid_arm_payload()
    (repo / auth.ARM_JSON_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / auth.ARM_JSON_REL).write_bytes(auth.canonical_json_bytes(payload))
    (repo / auth.ARM_MD_REL).write_text("# untracked\n", encoding="utf-8")
    # deliberately not committed
    _bind(monkeypatch, repo)
    with pytest.raises(auth.CollectionAuthorityError, match="UNTRACKED"):
        auth.authenticate_collection_arm()


# =============================================================================
# 6. Wrong collector HEAD/TREE refuses.
# =============================================================================


def test_arm_wrong_source_head_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    payload = _valid_arm_payload()
    payload["collector_source_head"] = "0" * 40
    _install_arm(repo, payload)
    _bind(monkeypatch, repo)
    with pytest.raises(auth.CollectionNotAuthorized, match="SOURCE_HEAD_MISMATCH"):
        auth.authenticate_collection_arm()


def test_arm_wrong_source_tree_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    payload = _valid_arm_payload()
    payload["collector_source_tree"] = "0" * 40
    _install_arm(repo, payload)
    _bind(monkeypatch, repo)
    with pytest.raises(auth.CollectionNotAuthorized, match="SOURCE_TREE_MISMATCH"):
        auth.authenticate_collection_arm()


def test_arm_wrong_run_identity_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    payload = _valid_arm_payload()
    payload["collection_run_identity"] = "0" * 64
    _install_arm(repo, payload)
    _bind(monkeypatch, repo)
    with pytest.raises(auth.CollectionNotAuthorized, match="RUN_IDENTITY_MISMATCH"):
        auth.authenticate_collection_arm()


def test_arm_not_authorized_flag_refused(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    payload = _valid_arm_payload()
    payload["authoritative_collection_authorized"] = False
    _install_arm(repo, payload)
    _bind(monkeypatch, repo)
    with pytest.raises(auth.CollectionNotAuthorized, match="NOT_AUTHORIZED"):
        auth.authenticate_collection_arm()


def test_no_git_root_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(root, "_repo_root", lambda: REPO)

    def _no_git(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(root.subprocess, "run", _no_git)
    with pytest.raises(root.ForwardObservabilityAuthorityRootError, match="GIT_VERIFICATION_REQUIRED"):
        root.verify_authority_root()


# =============================================================================
# 13. Source readiness fails if one of the 3 required sources is unavailable.
# =============================================================================


def test_readiness_fails_if_one_source_unavailable(monkeypatch, tmp_path):
    from scripts.research.forward_market_observability_v1.transport import (
        websocket_application_payload_bytes,
        rest_response_body_bytes,
    )

    config = default_config(root_dir=str(tmp_path))

    def fake_poll(*, config, sources, duration_seconds, stop_on_all_valid):
        # Simulate WS + one REST source healthy, the other REST unreachable.
        valid = {item["source_id"]: False for item in config["sources"]}
        for source_id in valid:
            if "MARK_PRICE" in source_id or "PREMIUM_INDEX" in source_id:
                valid[source_id] = True
        return valid

    monkeypatch.setattr(fwd_cli, "_poll_sources", fake_poll)
    args = fwd_cli.build_parser().parse_args(
        ["readiness", "--root", str(tmp_path), "--duration-seconds", "0.1"]
    )
    assert fwd_cli.cmd_readiness(args) == 1
    report = json.loads(
        next((tmp_path / "sessions").glob("*/READINESS.json")).read_text(encoding="utf-8")
    )
    assert report["all_frozen_sources_ready"] is False
    assert report["OPEN_INTEREST_NATIVE_READY"] is False


def test_all_three_sources_ready_reports_true(monkeypatch, tmp_path):
    config = default_config(root_dir=str(tmp_path))

    def fake_poll(*, config, sources, duration_seconds, stop_on_all_valid):
        return {item["source_id"]: True for item in config["sources"]}

    monkeypatch.setattr(fwd_cli, "_poll_sources", fake_poll)
    args = fwd_cli.build_parser().parse_args(
        ["readiness", "--root", str(tmp_path), "--duration-seconds", "0.1"]
    )
    assert fwd_cli.cmd_readiness(args) == 0


# =============================================================================
# 14. Smoke/readiness bytes remain scientifically excluded.
# =============================================================================


def test_readiness_session_is_scientifically_excluded_and_never_authoritative(
    monkeypatch, tmp_path
):
    config = default_config(root_dir=str(tmp_path))

    def fake_poll(*, config, sources, duration_seconds, stop_on_all_valid):
        return {item["source_id"]: True for item in config["sources"]}

    monkeypatch.setattr(fwd_cli, "_poll_sources", fake_poll)
    args = fwd_cli.build_parser().parse_args(
        ["readiness", "--root", str(tmp_path), "--duration-seconds", "0.1"]
    )
    fwd_cli.cmd_readiness(args)
    session_path = next((tmp_path / "sessions").glob("*/SESSION.json"))
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session["scientific_evidence"] is False
    assert session["authoritative_collection"] is False
    assert session["smoke_data_scientifically_excluded"] is True


def test_authoritative_session_cannot_carry_non_authoritative_label(tmp_path):
    from scripts.research.forward_market_observability_v1.session import (
        SessionError,
        INFRASTRUCTURE_SMOKE_TEST_ONLY,
        create_session,
    )

    config = default_config(root_dir=str(tmp_path))
    with pytest.raises(SessionError):
        create_session(
            repo=REPO,
            root=tmp_path,
            config=config,
            infrastructure_label=INFRASTRUCTURE_SMOKE_TEST_ONLY,
            authoritative_collection=True,
            collection_authority={"x": "y"},
        )


# =============================================================================
# 15. No predictive/scientific fields are computed anywhere here.
# =============================================================================


def test_no_scientific_computation_in_authority_module():
    """The authority module may DECLARE forbidden scientific field names
    (ARM_FORBIDDEN_FIELDS) but must never import a numeric/statistics
    library or perform arithmetic tied to them."""
    import ast
    import inspect

    source = inspect.getsource(auth)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            module = getattr(node, "module", None)
            forbidden_modules = {"numpy", "np", "pandas", "statistics", "scipy", "math"}
            assert not (forbidden_modules & set(names))
            assert module not in forbidden_modules
        assert not isinstance(node, (ast.BinOp, ast.Compare)) or not any(
            isinstance(n, ast.Name) and n.id.lower() in ("mae", "beta")
            for n in ast.walk(node)
        )

    # The forbidden-field names may appear only as declared string literals
    # (e.g. inside ARM_FORBIDDEN_FIELDS), never as identifiers/calls.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name:
                assert name.lower() not in ("mae", "beta", "prediction", "drawdown", "correlation")
