"""MARKET-01 implementation-freeze / ARM tests. Synthetic fixtures only.

Does not load CORE/OI snapshots, enumerate real episodes, or inspect
MARKET outcomes.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from scripts.research import market_01_oi_expansion_weak_continuation_authority as m01a
from scripts.research.market_01_oi_expansion_weak_continuation_authority import (
    ACCEPTED_IMPLEMENTATION_HEAD,
    ACCEPTED_IMPLEMENTATION_TREE,
    FROZEN_MARKET_01_RUN_IDENTITY,
    Market01ExecutionNotAuthorized,
    OI_SNAPSHOT_ID,
    PRICE_SNAPSHOT_ID,
    authenticate_market_01_arm,
    authenticate_market_01_canonical_execution,
    derive_market_01_run_identity,
    inspect_market_01_authorization_state,
)
from scripts.research.market_01_oi_expansion_weak_continuation_lib import (
    BAR_MS,
    COMMON_START_MS,
    FIVE_MS,
    OiView,
    PriceView,
    SYNTHETIC_SNAPSHOT,
    construct_episodes,
    evaluate_bound_market_01,
    evaluate_market_01,
)


REPO = Path(__file__).resolve().parents[2]
_TRACKED = (
    m01a.PREREG_MD_REL,
    m01a.PREREG_JSON_REL,
    m01a.PREREG_FREEZE_MD_REL,
    m01a.PREREG_FREEZE_JSON_REL,
    m01a.IMPL_FREEZE_JSON_REL,
    m01a.IMPL_FREEZE_MD_REL,
    m01a.ARM_JSON_REL,
    m01a.RESERVATION_JSON_REL,
    m01a.LIB_REL,
    m01a.B2_03_REL,
    m01a.V1_LIB_REL,
    m01a.V3_CONFIRMATORY_REL,
)


def _price(n: int, start_open_ms: int, closes: np.ndarray, snapshot: str) -> PriceView:
    open_ms = start_open_ms + np.arange(n, dtype=np.int64) * BAR_MS
    return PriceView(
        open_time_ms=open_ms,
        available_at_ms=open_ms + BAR_MS,
        close=np.asarray(closes, dtype=np.float64),
        snapshot_id=snapshot,
    )


def _oi(n: int, start_create_ms: int, values: np.ndarray, snapshot: str) -> OiView:
    create = start_create_ms + np.arange(n, dtype=np.int64) * FIVE_MS
    return OiView(
        create_time_ms=create,
        available_at_ms=create + FIVE_MS,
        sum_open_interest=np.asarray(values, dtype=np.float64),
        snapshot_id=snapshot,
    )


def _copy_live(rel: str, dest_root: Path) -> None:
    src = REPO / rel
    dest = dest_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


ARMED_EXECUTION_HEAD = "9e6f398e4d0a294adff317354c64fdbce91315a2"


def _copy_unused_arm_authority(rel: str, dest_root: Path) -> None:
    if rel in {m01a.ARM_JSON_REL, m01a.RESERVATION_JSON_REL}:
        data = subprocess.check_output(
            ["git", "-C", str(REPO), "show", f"{ARMED_EXECUTION_HEAD}:{rel}"]
        )
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return
    _copy_live(rel, dest_root)


def _bind(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(m01a, "_repo_root", lambda: repo)


def _armed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel in _TRACKED:
        _copy_unused_arm_authority(rel, repo)
    return repo


def test_live_arm_is_consumed_and_refuses_rerun():
    assert derive_market_01_run_identity() == FROZEN_MARKET_01_RUN_IDENTITY
    with pytest.raises(Market01ExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_01_arm()
    with pytest.raises(Market01ExecutionNotAuthorized):
        authenticate_market_01_canonical_execution()
    payload = json.loads((REPO / m01a.ARM_JSON_REL).read_text(encoding="utf-8"))
    for field in m01a.ARM_OUTCOME_FIELDS:
        assert field not in payload
    assert payload["run_identity"] == FROZEN_MARKET_01_RUN_IDENTITY
    assert payload["authorization_consumed"] is True
    state = inspect_market_01_authorization_state()
    assert state["MARKET_01_EXECUTION_AUTHORIZED"] is False
    assert state["MARKET_01_TEST_CALIBRATED"] is False


def test_unarmed_bound_execution_refuses():
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), SYNTHETIC_SNAPSHOT)
    with pytest.raises(Market01ExecutionNotAuthorized):
        construct_episodes(price, oi)
    with pytest.raises(Market01ExecutionNotAuthorized):
        evaluate_bound_market_01()


def test_unarmed_repo_refuses_bound_pair(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    (repo / m01a.ARM_JSON_REL).unlink()
    _bind(monkeypatch, repo)
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market01ExecutionNotAuthorized):
        construct_episodes(price, oi)
    state = inspect_market_01_authorization_state()
    assert state["MARKET_01_ARMED"] is False


def test_wrong_arm_identity_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m01a.ARM_JSON_REL).read_text(encoding="utf-8"))
    payload["freeze_artifact_sha256"] = "0" * 64
    (repo / m01a.ARM_JSON_REL).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _bind(monkeypatch, repo)
    with pytest.raises(Market01ExecutionNotAuthorized, match="ARM_IDENTITY"):
        authenticate_market_01_arm()
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market01ExecutionNotAuthorized):
        construct_episodes(price, oi)


def test_wrong_run_identity_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m01a.ARM_JSON_REL).read_text(encoding="utf-8"))
    payload["run_identity"] = "0" * 64
    (repo / m01a.ARM_JSON_REL).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _bind(monkeypatch, repo)
    with pytest.raises(Market01ExecutionNotAuthorized, match="RUN_IDENTITY"):
        authenticate_market_01_arm()


def test_wrong_implementation_identity_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    target = repo / m01a.LIB_REL
    target.write_bytes(target.read_bytes() + b"\n# mutated\n")
    _bind(monkeypatch, repo)
    with pytest.raises(m01a.Market01AuthorityError, match="BYTE_IDENTITY"):
        authenticate_market_01_arm()
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market01ExecutionNotAuthorized):
        construct_episodes(price, oi)


def test_wrong_snapshot_identity_refuses():
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), "not-the-oi-snapshot")
    with pytest.raises(Market01ExecutionNotAuthorized, match="SNAPSHOT"):
        construct_episodes(price, oi)


def test_bound_snapshots_refuse_after_canonical_consumption():
    price = _price(120, COMMON_START_MS, np.full(120, 100.0), PRICE_SNAPSHOT_ID)
    oi = _oi(30, COMMON_START_MS, np.full(30, 10.0), OI_SNAPSHOT_ID)
    with pytest.raises(Market01ExecutionNotAuthorized):
        construct_episodes(price, oi)
    with pytest.raises(Market01ExecutionNotAuthorized):
        evaluate_bound_market_01(price, oi)


def test_synthetic_unbound_pipeline_still_runs_after_consumption():
    price = _price(120, COMMON_START_MS, np.full(120, 100.0), SYNTHETIC_SNAPSHOT)
    oi = _oi(30, COMMON_START_MS, np.full(30, 10.0), SYNTHETIC_SNAPSHOT)
    result = evaluate_market_01(price, oi)
    assert result["final_classification"] == "NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT"
    assert result["MARKET_01_TEST_CALIBRATED"] is False
    assert result["DEFAULT_V4"] is False
    assert result["B2_06_EXECUTION_AUTHORIZED"] is False
    assert result["PROTECTED_OOS_TOUCHED"] is False
    assert result["episode_diagnostics"]["n_confirmatory_eligible"] == 0


def test_caller_kwargs_cannot_replace_authority():
    with pytest.raises(Market01ExecutionNotAuthorized, match="caller arguments"):
        authenticate_market_01_arm(run_identity="forged")
    with pytest.raises(Market01ExecutionNotAuthorized, match="caller arguments"):
        derive_market_01_run_identity("forged")
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market01ExecutionNotAuthorized):
        evaluate_bound_market_01(price, oi, windows=30)


def test_consumed_reservation_refuses_rerun(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m01a.RESERVATION_JSON_REL).read_text(encoding="utf-8"))
    payload["CANONICAL_EXECUTIONS_CONSUMED"] = 1
    (repo / m01a.RESERVATION_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market01ExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_01_canonical_execution()


def _fn_source(tree: ast.AST, name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(name)


def test_scientific_functions_match_accepted_implementation_head():
    old = subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"{ACCEPTED_IMPLEMENTATION_HEAD}:{m01a.LIB_REL}"]
    )
    new = (REPO / m01a.LIB_REL).read_bytes()
    old_tree = ast.parse(old)
    new_tree = ast.parse(new)
    for name in (
        "midrank_percentile",
        "close_at",
        "legal_oi_at",
        "pre_vol_60",
        "classify_qualifying_impulse",
        "classify_oi_expansion",
        "classify_weak_continuation",
        "assign_stratum",
        "reversal_return",
        "construct_episodes",
        "usable_strata",
        "support_gate",
        "design_matrix",
        "fit_stratified_ols",
        "frisch_waugh_influence",
        "_draw_indices",
        "one_sided_p",
        "run_stationary_bootstrap",
        "loeo_sign_stable",
        "concentration",
        "final_classification",
        "evaluate_from_confirmatory_rows",
        "evaluate_market_01",
    ):
        assert _fn_source(old_tree, name) == _fn_source(new_tree, name), name


def test_accepted_implementation_identity_is_bound():
    freeze = json.loads((REPO / m01a.IMPL_FREEZE_JSON_REL).read_text(encoding="utf-8"))
    assert freeze["reviewed_implementation"]["head"] == ACCEPTED_IMPLEMENTATION_HEAD
    assert freeze["reviewed_implementation"]["tree"] == ACCEPTED_IMPLEMENTATION_TREE
    arm = json.loads((REPO / m01a.ARM_JSON_REL).read_text(encoding="utf-8"))
    assert arm["run_identity"] == FROZEN_MARKET_01_RUN_IDENTITY
    reservation = json.loads((REPO / m01a.RESERVATION_JSON_REL).read_text(encoding="utf-8"))
    assert reservation["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert reservation["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    assert reservation["rerun_preauthorized"] is False
