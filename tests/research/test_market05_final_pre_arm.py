"""MARKET-05 final pre-ARM adversarial tests.

Synthetic/fixture only. No real MARKET-05 Y/MAE/coefficient inspection.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.research import market05_cross_asset_arm_authority as m05arm
from scripts.research import market05_cross_asset_authority_root as m05root
from scripts.research import market05_cross_asset_canonical_execution as m05exec
from scripts.research import market05_cross_asset_data_preflight as m05pre
from scripts.research import market05_cross_asset_execution_claim as m05claim
from scripts.research import market05_cross_asset_lib as m05lib
from scripts.research import market05_eth_execution_binding as m05eth
from tests.research.test_market05_arm_lifecycle import (
    _armed_repo,
    _bind,
    _synthetic_rows,
    _valid_arm_payload,
)

REPO = Path(__file__).resolve().parents[2]


def _write_ohlc_parquet(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "open_time_ms": pa.array([r["open_time_ms"] for r in rows], type=pa.int64()),
            "high": pa.array([str(r["high"]) for r in rows], type=pa.string()),
            "low": pa.array([str(r["low"]) for r in rows], type=pa.string()),
            "close": pa.array([str(r["close"]) for r in rows], type=pa.string()),
        }
    )
    pq.write_table(table, path, **m05eth.PARQUET_WRITE_KWARGS)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_two_concurrent_claims_exactly_one_succeeds(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    bound = m05arm.authenticate_market_05_pre_claim()
    payload = bound["claim_payload"]
    results: list[str] = []

    def worker() -> None:
        try:
            m05claim.create_execution_claim_atomically(payload)
            results.append("win")
        except m05claim.Market05ExecutionClaimError:
            results.append("lose")

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert results.count("win") == 1
    assert results.count("lose") == 1
    loaded: list[str] = []

    def would_load() -> None:
        loaded.append("loaded")

    def loser_path() -> None:
        try:
            m05claim.create_execution_claim_atomically(payload)
            would_load()
        except m05claim.Market05ExecutionClaimError:
            return

    loser_path()
    assert loaded == []
    assert m05arm.market_05_execution_is_authorized() is False


@pytest.mark.parametrize(
    "result_state",
    ["none", "partial_json", "complete"],
)
def test_claim_blocks_rerun_for_every_result_state(tmp_path, monkeypatch, result_state):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    m05arm.consume_authorization_atomically()
    json_path = repo / m05arm.RESULT_JSON_REL
    md_path = repo / m05arm.RESULT_MD_REL
    json_path.parent.mkdir(parents=True, exist_ok=True)
    if result_state == "partial_json":
        json_path.write_text("{", encoding="utf-8")
    elif result_state == "complete":
        json_path.write_text("{}\n", encoding="utf-8")
        md_path.write_text("# result\n", encoding="utf-8")
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="CLAIMED"
    ):
        m05arm.authenticate_market_05_pre_claim()
    assert m05arm.market_05_execution_is_authorized() is False


def test_synthetic_success_path_claim_then_result_without_reauth_failure(
    tmp_path, monkeypatch
):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    m05arm.consume_authorization_atomically()
    result = m05exec.execute_synthetic_after_claim(_synthetic_rows())
    assert result["result_status"] == "COMPLETE"
    assert result["maes"]["POOLED_MAE_BASELINE"] is not None
    assert result["coefficients"]["BETA_ETH_CONFIRMATION"] is not None
    assert result["year_metrics"][2022] is not None
    assert result["classification"] in {
        m05lib.CLASS_PROMOTED,
        m05lib.CLASS_NO_EVIDENCE,
        m05lib.CLASS_INCOMPLETE,
    }
    with pytest.raises(m05exec.Market05CanonicalExecutionError):
        m05exec.execute_synthetic_after_claim(_synthetic_rows())


def test_production_parquet_reader_uses_low_and_high(tmp_path):
    path = tmp_path / "bars.parquet"
    t = m05lib.FIRST_USABLE_MS
    rows = []
    for i in range(10):
        rows.append(
            {
                "open_time_ms": t + i * 60_000,
                "high": "110.0",
                "low": "90.0",
                "close": "100.0",
            }
        )
    _write_ohlc_parquet(path, rows)
    bars = m05exec._read_bars([path], dataset_id="FIXTURE")
    first = bars[t]
    assert first.high == 110.0
    assert first.low == 90.0
    assert first.close == 100.0
    up = m05lib.direction_aligned_mae(1.0, 100.0, [90.0] * 1440, [110.0] * 1440)
    down = m05lib.direction_aligned_mae(-1.0, 100.0, [90.0] * 1440, [110.0] * 1440)
    assert up is not None and down is not None
    assert abs(up - __import__("math").log(100.0 / 90.0)) < 1e-12
    assert abs(down - __import__("math").log(110.0 / 100.0)) < 1e-12


def test_missing_required_btc_month_fails_before_claim(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    monkeypatch.setattr(
        m05pre,
        "btc_development_parquet_rels",
        lambda snapshot: ["canonical/1m/monthly/2020-01.parquet"],
    )
    monkeypatch.setattr(
        m05pre,
        "verify_eth_execution_binding",
        lambda: {"eth_objects": [], "eth_object_count": 60, "eth_execution_data_id": "x"},
    )
    with pytest.raises(m05pre.Market05PreflightError, match="INCOMPLETE|MISSING"):
        m05pre.verify_btc_development_set()
    assert m05claim.claim_exists() is False


def test_altered_btc_parquet_checksum_fails_before_claim(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    rel = "canonical/1m/monthly/2020-01.parquet"
    dest = repo / "artifacts/research_data/CORE_BTC_BINANCE_V0" / rel
    _write_ohlc_parquet(dest, [{"open_time_ms": 1, "high": "1", "low": "1", "close": "1"}])
    snapshot = {
        "identity_payload": {
            "output_checksums": {rel: "0" * 64},
        }
    }
    (repo / m05arm.BTC_SNAPSHOT_DOC_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / m05arm.BTC_SNAPSHOT_DOC_REL).write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(m05pre, "btc_development_parquet_rels", lambda s: [rel])
    with pytest.raises(m05pre.Market05PreflightError, match="CHECKSUM_MISMATCH"):
        m05pre.verify_btc_development_set()
    assert not m05claim.claim_exists()


def test_altered_eth_execution_parquet_fails_before_claim(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    binding = json.loads((REPO / m05arm.ETH_EXECUTION_BINDING_REL).read_text())
    obj = dict(binding["objects"][0])
    rel = obj["canonical_parquet_relative_path"]
    dest = repo / m05eth.ETH_PARQUET_ROOT_REL / rel
    _write_ohlc_parquet(
        dest,
        [
            {
                "open_time_ms": obj["first_open_time_ms"],
                "high": "1",
                "low": "1",
                "close": "1",
            }
        ],
    )
    obj["canonical_parquet_sha256"] = "0" * 64
    obj["row_count"] = 1
    obj["last_open_time_ms"] = obj["first_open_time_ms"]
    fake = {
        k: v
        for k, v in binding.items()
        if k != "eth_execution_data_id"
    }
    fake["objects"] = [obj]
    fake["object_count"] = 1
    ident = hashlib.sha256(m05eth.canonical_json_bytes(fake)).hexdigest()
    fake["eth_execution_data_id"] = ident
    (repo / m05arm.ETH_EXECUTION_BINDING_REL).write_bytes(m05eth.canonical_json_bytes(fake))
    with pytest.raises(m05pre.Market05PreflightError, match="CHECKSUM_MISMATCH"):
        m05pre.verify_eth_execution_binding()
    assert not m05claim.claim_exists()


def test_eth_execution_manifest_binds_original_accepted_zip():
    binding = m05eth.load_execution_binding(REPO)
    snapshot = json.loads((REPO / m05eth.ETH_SNAPSHOT_DOC_REL).read_text())
    zip_by_name = {
        obj["expected_zip_filename"]: obj["zip_sha256"] for obj in snapshot["objects"]
    }
    assert binding["object_count"] == 60
    for obj in binding["objects"]:
        assert obj["source_zip_sha256"] == zip_by_name[obj["source_official_zip_filename"]]
        assert not obj["source_period"].startswith("2025")
        assert not obj["source_period"].startswith("2026")


def test_wrong_numpy_version_refuses_before_claim(monkeypatch):
    import numpy

    monkeypatch.setattr(numpy, "__version__", "9.9.9")
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="NUMPY_VERSION"
    ):
        m05arm.verify_execution_environment()
    assert not m05claim.claim_exists()


def test_wrong_pyarrow_version_refuses_before_claim(monkeypatch):
    monkeypatch.setattr(sys.modules["pyarrow"], "__version__", "0.0.0")
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="PYARROW_VERSION"
    ):
        m05arm.verify_execution_environment()
    assert not m05claim.claim_exists()


def test_preloaded_scientific_module_refuses_canonical_bootstrap():
    script = r"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(%r).resolve()))
import scripts.research.market05_cross_asset_lib  # noqa: F401
from scripts.research.market05_cross_asset_bootstrap import (
    Market05BootstrapError,
    run_canonical_market_05_bootstrap,
)
try:
    run_canonical_market_05_bootstrap()
except Market05BootstrapError as exc:
    print(str(exc))
    raise SystemExit(0)
raise SystemExit(1)
""" % str(REPO)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "MARKET_05_SCIENTIFIC_MODULE_PRELOADED" in proc.stdout


def test_git_replace_cannot_satisfy_frozen_root(tmp_path, monkeypatch):
    from tests.research.test_market05_arm_lifecycle import _fixture_repo

    repo = _fixture_repo(tmp_path)
    monkeypatch.setattr(m05root, "_repo_root", lambda: repo)
    root_rel = m05root.AUTHORITY_ROOT_REL
    original = (repo / root_rel).read_bytes()
    original_blob = subprocess.run(
        ["git", "hash-object", str(repo / root_rel)],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    mutated = original + b"\n# replaced\n"
    (repo / root_rel).write_bytes(mutated)
    fake_blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=str(repo),
        input=mutated,
        check=True,
        capture_output=True,
    ).stdout.decode().strip()
    subprocess.run(
        ["git", "replace", original_blob, fake_blob],
        cwd=str(repo),
        check=False,
        capture_output=True,
    )
    with pytest.raises(m05root.Market05AuthorityRootError, match="SELF_MUTATED"):
        m05root.verify_authority_root()


def test_git_object_directory_override_ignored(tmp_path, monkeypatch):
    empty = tmp_path / "objects"
    empty.mkdir()
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(empty))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "not-a-repo"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path))
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", str(empty))
    out = m05root.verify_authority_root()
    assert out["git_verified"] is True


def test_alternate_worktree_redirection_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "other-worktree"))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "other.git"))
    out = m05root.verify_authority_root()
    assert out["git_verified"] is True
    assert out["scientific_implementation_head"] == m05root.load_frozen_provenance()["head"]


def test_result_contains_every_statistic_used_for_classification():
    rows = _synthetic_rows()
    evaluation = m05lib.evaluate_prepared_rows(
        rows, predictive_replicates=8, coefficient_replicates=8
    )
    for key in (
        "POOLED_MAE_BASELINE",
        "POOLED_MAE_CANDIDATE",
        "RELATIVE_MAE_IMPROVEMENT",
        "YEAR_RELATIVE_MAE_IMPROVEMENT",
        "BETA_ETH_CONFIRMATION",
        "BETA_ETH_CONFIRMATION_CI",
        "RELATIVE_MAE_IMPROVEMENT_CI",
        "folds",
        "gates",
        "classification",
    ):
        assert evaluation[key] is not None


def test_complete_result_with_none_metric_refused(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    m05arm.consume_authorization_atomically()
    payload = {key: None for key in m05lib.RESULT_SCHEMA_KEYS}
    payload["result_status"] = "COMPLETE"
    payload["classification"] = m05lib.CLASS_NO_EVIDENCE
    payload["run_identity"] = m05arm.derive_market_05_run_identity()
    with pytest.raises(m05lib.Market05IntegrityError, match="INCOMPLETE"):
        m05lib.instantiate_scientific_result(payload)


def test_protected_oos_ohlc_never_parsed(tmp_path):
    path = tmp_path / "2024-12.parquet"
    oos = m05lib.PROTECTED_OOS_START_MS
    _write_ohlc_parquet(
        path,
        [{"open_time_ms": oos, "high": "1", "low": "1", "close": "1"}],
    )
    with pytest.raises(Exception, match="PROTECTED_OOS"):
        m05exec._read_bars([path], dataset_id="FIXTURE")


def test_eth_binding_id_is_canonical():
    binding = json.loads((REPO / m05arm.ETH_EXECUTION_BINDING_REL).read_text())
    stored = binding.pop("eth_execution_data_id")
    recomputed = hashlib.sha256(m05eth.canonical_json_bytes(binding)).hexdigest()
    assert stored == recomputed == m05arm.ETH_EXECUTION_DATA_ID


@pytest.mark.parametrize(
    "stage",
    [
        "after_claim",
        "during_load",
        "during_eval",
        "after_eval_before_result",
        "after_json_before_md",
        "after_full_result",
    ],
)
def test_crash_after_claim_never_restores_authorization(tmp_path, monkeypatch, stage):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    m05arm.consume_authorization_atomically()
    json_path = repo / m05arm.RESULT_JSON_REL
    md_path = repo / m05arm.RESULT_MD_REL
    if stage == "after_json_before_md":
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text('{"result_status": "INCOMPLETE_OR_UNKNOWN"}\n', encoding="utf-8")
    elif stage == "after_full_result":
        m05exec.execute_synthetic_after_claim(_synthetic_rows())
        assert json_path.is_file()
        assert md_path.is_file()
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="CLAIMED"
    ):
        m05arm.authenticate_market_05_pre_claim()
    assert m05arm.market_05_execution_is_authorized() is False
    assert m05claim.claim_exists()
    status = m05claim.canonical_result_integrity_status()
    if stage == "after_full_result":
        assert status == "COMPLETE"
        classification = json.loads(json_path.read_text())["classification"]
        assert classification in {
            m05lib.CLASS_PROMOTED,
            m05lib.CLASS_NO_EVIDENCE,
            m05lib.CLASS_INCOMPLETE,
        }
    else:
        assert status == "MARKET_05_INCOMPLETE_EXECUTION"
        if json_path.exists():
            payload = json.loads(json_path.read_text())
            assert payload.get("classification") not in {
                m05lib.CLASS_PROMOTED,
                m05lib.CLASS_NO_EVIDENCE,
            }


def test_deleting_result_does_not_restore_authorization(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    m05arm.consume_authorization_atomically()
    m05exec.execute_synthetic_after_claim(_synthetic_rows())
    (repo / m05arm.RESULT_JSON_REL).unlink()
    (repo / m05arm.RESULT_MD_REL).unlink()
    assert m05claim.claim_exists()
    assert m05arm.market_05_execution_is_authorized() is False
    with pytest.raises(
        m05arm.Market05CanonicalExecutionNotAuthorized, match="CLAIMED"
    ):
        m05arm.authenticate_market_05_pre_claim()
    assert m05claim.canonical_result_integrity_status() == "MARKET_05_INCOMPLETE_EXECUTION"


def test_production_api_does_not_delete_claim():
    assert not hasattr(m05claim, "delete_execution_claim")
    assert not hasattr(m05arm, "delete_execution_claim")
