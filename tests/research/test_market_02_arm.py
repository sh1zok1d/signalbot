"""MARKET-02 ARM tests. Synthetic fixtures only.

Does not load CORE/OI snapshots, enumerate real episodes, inspect real
MARKET-02 outcomes, or trigger canonical execution.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from scripts.research import market_02_oi_expansion_price_confirmation_authority as m02a
from scripts.research.market_02_oi_expansion_price_confirmation_authority import (
    FROZEN_IMPLEMENTATION_HEAD,
    FROZEN_IMPLEMENTATION_TREE,
    FROZEN_MARKET_02_RUN_IDENTITY,
    Market02AuthorityError,
    Market02ExecutionNotAuthorized,
    Market02NotArmed,
    OI_SNAPSHOT_ID,
    PRICE_SNAPSHOT_ID,
    REVIEWED_IMPLEMENTATION_HEAD,
    authenticate_market_02_arm,
    authenticate_market_02_canonical_execution,
    derive_market_02_run_identity,
    inspect_market_02_authorization_state,
)
from scripts.research.market_02_oi_expansion_price_confirmation_lib import (
    BAR_MS,
    COMMON_START_MS,
    FIVE_MS,
    MARKET_02_TEST_CALIBRATED,
    OiView,
    PriceView,
    SYNTHETIC_SNAPSHOT,
    construct_episodes,
    evaluate_bound_market_02,
    evaluate_market_02,
)


REPO = Path(__file__).resolve().parents[2]
_TRACKED = (
    m02a.PREREG_MD_REL,
    m02a.PREREG_JSON_REL,
    m02a.IMPL_FREEZE_JSON_REL,
    m02a.IMPL_FREEZE_MD_REL,
    m02a.ARM_JSON_REL,
    m02a.RESERVATION_JSON_REL,
    m02a.LIB_REL,
    m02a.FAST_PRECOMPUTE_REL,
    m02a.M01_LIB_REL,
    m02a.B2_03_REL,
    m02a.V1_LIB_REL,
    m02a.V3_CONFIRMATORY_REL,
    m02a.CORE_SNAPSHOT_IDENTITY_REL,
    m02a.CORE_MANIFEST_REL,
    m02a.OI_SNAPSHOT_IDENTITY_REL,
    m02a.OI_MANIFEST_REL,
)
SCIENTIFIC_FNS = (
    "classify_price_confirmation",
    "continuation_return",
    "construct_episodes",
    "confirmatory_rows",
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
    "detected_rule",
    "final_classification",
    "evaluate_from_confirmatory_rows",
    "evaluate_market_02",
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


ARMED_EXECUTION_HEAD = "6486dfadd920fc24a72fabe37d7dd906154cbc76"


def _copy_unused_arm_authority(rel: str, dest_root: Path) -> None:
    if rel in {m02a.ARM_JSON_REL, m02a.RESERVATION_JSON_REL}:
        data = subprocess.check_output(
            ["git", "-C", str(REPO), "show", f"{ARMED_EXECUTION_HEAD}:{rel}"]
        )
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return
    _copy_live(rel, dest_root)


def _bind(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(m02a, "_repo_root", lambda: repo)


def _armed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel in _TRACKED:
        _copy_unused_arm_authority(rel, repo)
    return repo


def test_live_arm_is_consumed_and_refuses_rerun():
    assert derive_market_02_run_identity() == FROZEN_MARKET_02_RUN_IDENTITY
    with pytest.raises(Market02ExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_02_arm()
    with pytest.raises(Market02ExecutionNotAuthorized):
        authenticate_market_02_canonical_execution()
    payload = json.loads((REPO / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    for field in m02a.ARM_OUTCOME_FIELDS:
        assert field not in payload
    assert payload["run_identity"] == FROZEN_MARKET_02_RUN_IDENTITY
    assert payload["authorization_consumed"] is True
    reservation = json.loads((REPO / m02a.RESERVATION_JSON_REL).read_text(encoding="utf-8"))
    assert reservation["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert reservation["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    state = inspect_market_02_authorization_state()
    assert state["MARKET_02_EXECUTION_AUTHORIZED"] is False
    assert state["MARKET_02_TEST_CALIBRATED"] is False
    assert (REPO / m02a.RESULT_JSON_REL).exists() is True


def test_unarmed_repo_refuses_bound_pair(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    (repo / m02a.ARM_JSON_REL).unlink()
    _bind(monkeypatch, repo)
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market02NotArmed, match="MARKET_02_NOT_ARMED"):
        construct_episodes(price, oi)
    state = inspect_market_02_authorization_state()
    assert state["MARKET_02_ARMED"] is False
    assert state["MARKET_02_EXECUTION_AUTHORIZED"] is False


def test_wrong_arm_bytes_refuse(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    payload["freeze_artifact_sha256"] = "0" * 64
    (repo / m02a.ARM_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market02ExecutionNotAuthorized, match="ARM_IDENTITY"):
        authenticate_market_02_arm()
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market02ExecutionNotAuthorized):
        construct_episodes(price, oi)


def test_wrong_run_identity_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    payload["run_identity"] = "0" * 64
    (repo / m02a.ARM_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market02ExecutionNotAuthorized, match="RUN_IDENTITY"):
        authenticate_market_02_arm()


def test_wrong_implementation_head_tree_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    payload["frozen_implementation_head"] = "0" * 40
    payload["frozen_implementation_tree"] = "0" * 40
    (repo / m02a.ARM_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market02ExecutionNotAuthorized, match="IMPLEMENTATION"):
        authenticate_market_02_arm()
    payload = json.loads((repo / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    live = json.loads((REPO / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    payload["frozen_implementation_head"] = live["frozen_implementation_head"]
    payload["frozen_implementation_tree"] = live["frozen_implementation_tree"]
    payload["reviewed_implementation_head"] = "0" * 40
    (repo / m02a.ARM_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    with pytest.raises(Market02ExecutionNotAuthorized, match="IMPLEMENTATION"):
        authenticate_market_02_arm()


def test_changed_scientific_lib_bytes_refuse(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    target = repo / m02a.LIB_REL
    target.write_bytes(target.read_bytes() + b"\n# mutated\n")
    _bind(monkeypatch, repo)
    with pytest.raises(m02a.Market02AuthorityError, match="BYTE_IDENTITY"):
        authenticate_market_02_arm()
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market02ExecutionNotAuthorized):
        construct_episodes(price, oi)


def test_changed_prereg_bytes_refuse(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    target = repo / m02a.PREREG_MD_REL
    target.write_bytes(target.read_bytes() + b"\n")
    _bind(monkeypatch, repo)
    with pytest.raises(Market02AuthorityError, match="PREREG"):
        authenticate_market_02_arm()


def test_wrong_core_snapshot_refuses():
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), "not-the-core-snapshot")
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market02ExecutionNotAuthorized, match="SNAPSHOT"):
        construct_episodes(price, oi)


def test_wrong_oi_snapshot_refuses():
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), "not-the-oi-snapshot")
    with pytest.raises(Market02ExecutionNotAuthorized, match="SNAPSHOT"):
        construct_episodes(price, oi)


def test_unbound_replacement_snapshots_do_not_use_arm_gate():
    price = _price(120, COMMON_START_MS, np.full(120, 100.0), SYNTHETIC_SNAPSHOT)
    oi = _oi(30, COMMON_START_MS, np.full(30, 10.0), SYNTHETIC_SNAPSHOT)
    result = evaluate_market_02(price, oi)
    assert result["final_classification"] == "NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT"
    assert result["MARKET_02_TEST_CALIBRATED"] is False
    assert result["PROTECTED_OOS_TOUCHED"] is False


def test_unbound_replacement_cannot_authorize_as_bound(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), SYNTHETIC_SNAPSHOT)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), SYNTHETIC_SNAPSHOT)
    with pytest.raises(Market02ExecutionNotAuthorized, match="SNAPSHOT"):
        m02a.authorize_bound_market_02_views(price.snapshot_id, oi.snapshot_id)


def test_exact_snapshot_identity_after_arm_synthetic_views_only(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    _bind(monkeypatch, repo)
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    episodes = construct_episodes(price, oi)
    assert isinstance(episodes, list)
    # Tiny synthetic series; no CORE/OI load and no second canonical RESULT.


def test_wrong_execution_seed_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    payload["MARKET_02_BOOTSTRAP_SEED"] = "1852983754304692000"
    (repo / m02a.ARM_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market02ExecutionNotAuthorized, match="SEED"):
        authenticate_market_02_arm()


def test_wrong_result_authority_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    payload["result_artifact_path"] = "docs/research/NOT_THE_MARKET_02_RESULT.json"
    (repo / m02a.ARM_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market02ExecutionNotAuthorized, match="RESULT_AUTHORITY"):
        authenticate_market_02_arm()


def test_wrong_reservation_authority_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m02a.RESERVATION_JSON_REL).read_text(encoding="utf-8"))
    payload["arm_artifact_sha256"] = "0" * 64
    (repo / m02a.RESERVATION_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market02ExecutionNotAuthorized, match="RESERVATION_ARM"):
        authenticate_market_02_canonical_execution()


def test_second_canonical_execution_after_consumption_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    payload = json.loads((repo / m02a.RESERVATION_JSON_REL).read_text(encoding="utf-8"))
    payload["CANONICAL_EXECUTIONS_CONSUMED"] = 1
    (repo / m02a.RESERVATION_JSON_REL).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _bind(monkeypatch, repo)
    with pytest.raises(Market02ExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_02_canonical_execution()
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market02ExecutionNotAuthorized):
        construct_episodes(price, oi)


def test_protected_oos_substitution_refuses():
    oos_id = "protected-2025-2026-oos-not-authorized"
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), oos_id)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market02ExecutionNotAuthorized, match="SNAPSHOT"):
        construct_episodes(price, oi)
    with pytest.raises(Market02ExecutionNotAuthorized, match="SNAPSHOT"):
        m02a.authorize_bound_market_02_views(oos_id, OI_SNAPSHOT_ID)


def test_wrong_core_identity_doc_refuses(tmp_path, monkeypatch):
    repo = _armed_repo(tmp_path)
    target = repo / m02a.CORE_SNAPSHOT_IDENTITY_REL
    target.write_bytes(target.read_bytes() + b"\n")
    _bind(monkeypatch, repo)
    with pytest.raises(Market02AuthorityError, match="BYTE_IDENTITY"):
        authenticate_market_02_arm()


def test_evaluate_bound_rejects_kwargs_and_missing_views():
    with pytest.raises(Market02ExecutionNotAuthorized):
        evaluate_bound_market_02()
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market02ExecutionNotAuthorized):
        evaluate_bound_market_02(price, oi, windows=30)
    with pytest.raises(Market02ExecutionNotAuthorized, match="caller arguments"):
        authenticate_market_02_arm(run_identity="forged")
    with pytest.raises(Market02ExecutionNotAuthorized, match="caller arguments"):
        derive_market_02_run_identity("forged")


def test_caller_kwargs_cannot_replace_authority():
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]), PRICE_SNAPSHOT_ID)
    oi = _oi(1, COMMON_START_MS, np.array([1.0]), OI_SNAPSHOT_ID)
    with pytest.raises(Market02ExecutionNotAuthorized):
        evaluate_bound_market_02(price, oi, windows=30)


def _fn_source(tree: ast.AST, name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(name)


def test_scientific_functions_match_reviewed_implementation_head():
    old = subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"{REVIEWED_IMPLEMENTATION_HEAD}:{m02a.LIB_REL}"]
    )
    new = (REPO / m02a.LIB_REL).read_bytes()
    old_tree = ast.parse(old)
    new_tree = ast.parse(new)
    for name in SCIENTIFIC_FNS:
        assert _fn_source(old_tree, name) == _fn_source(new_tree, name), name


def test_frozen_implementation_identity_is_bound():
    freeze = json.loads((REPO / m02a.IMPL_FREEZE_JSON_REL).read_text(encoding="utf-8"))
    assert freeze["reviewed_implementation"]["head"] == REVIEWED_IMPLEMENTATION_HEAD
    arm = json.loads((REPO / m02a.ARM_JSON_REL).read_text(encoding="utf-8"))
    assert arm["run_identity"] == FROZEN_MARKET_02_RUN_IDENTITY
    assert arm["frozen_implementation_head"] == FROZEN_IMPLEMENTATION_HEAD
    assert arm["frozen_implementation_tree"] == FROZEN_IMPLEMENTATION_TREE
    assert arm["lib_reviewed_sha256"] == m02a.LIB_REVIEWED_SHA256
    assert arm["lib_armed_lifecycle_sha256"] == m02a.LIB_ARMED_LIFECYCLE_SHA256
    reservation = json.loads((REPO / m02a.RESERVATION_JSON_REL).read_text(encoding="utf-8"))
    assert reservation["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert reservation["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    assert reservation["rerun_preauthorized"] is False
