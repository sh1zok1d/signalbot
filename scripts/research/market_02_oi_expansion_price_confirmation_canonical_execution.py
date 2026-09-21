#!/usr/bin/env python3
"""One-shot canonical MARKET-02 execution.

Does not accept scientific kwargs. Does not preview/smoke real MARKET data.
Consumes the unused reservation no later than the first call to
evaluate_bound_market_02. Never reruns. Does not open protected 2025/2026 OOS.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from scripts.research.h01_compression_expansion_lib import (
    list_development_parquet_paths,
    parse_px,
)
from scripts.research.market_02_oi_expansion_price_confirmation_authority import (
    ARM_JSON_REL,
    ARM_JSON_SHA256,
    B2_03_SHA256,
    B2_06_EXECUTION_AUTHORIZED,
    CANONICAL_EXECUTIONS_AUTHORIZED,
    COMMON_END_EXCLUSIVE,
    COMMON_START_INCLUSIVE,
    CORE_SNAPSHOT_IDENTITY_SHA256,
    DEFAULT_V4,
    FROZEN_IMPLEMENTATION_HEAD,
    FROZEN_IMPLEMENTATION_TREE,
    FROZEN_MARKET_02_RUN_IDENTITY,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    IMPL_FREEZE_JSON_SHA256,
    LIB_ARMED_LIFECYCLE_SHA256,
    LIB_REVIEWED_SHA256,
    MARKET_02_BOOTSTRAP_SEED,
    MARKET_02_TEST_CALIBRATED,
    OI_SNAPSHOT_IDENTITY_SHA256,
    OI_SNAPSHOT_ID,
    PRICE_DATASET_ID,
    PRICE_SNAPSHOT_ID,
    PROTECTED_OOS_AUTHORIZED,
    RESEARCH_ID,
    RESERVATION_JSON_REL,
    RESERVATION_JSON_SHA256,
    RESULT_JSON_REL,
    SEED_MATERIAL,
    SEED_MATERIAL_SHA256,
    V1_LIB_SHA256,
    V3_SELECTOR_MODULE_SHA256,
    authenticate_market_02_canonical_execution,
    canonical_json_bytes,
    sha256_file,
)
from scripts.research.market_02_oi_expansion_price_confirmation_lib import (
    OiView,
    PriceView,
    dumps_result,
    evaluate_bound_market_02,
)

REPO = Path(__file__).resolve().parents[2]
ARMED_HEAD = "6486dfadd920fc24a72fabe37d7dd906154cbc76"
ARMED_TREE = "6f022334ea015756c8551bad73debed81ba4f8a9"
CORE_ROOT = REPO / "artifacts" / "research_data" / "CORE_BTC_BINANCE_V0"
OI_ROOT = REPO / "artifacts" / "research_data" / "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
CORE_SNAPSHOT_DOC = (
    REPO / "docs" / "research_data" / "CORE_BTC_BINANCE_V0" / "SNAPSHOT_717d37a4.json"
)
OI_SNAPSHOT_DOC = (
    REPO
    / "docs"
    / "research_data"
    / "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
    / "SNAPSHOT_5a9d036b.json"
)
LOCK_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_CONSUMPTION_LOCK.json"
RESULT_REL = RESULT_JSON_REL
FAILURE_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_EXECUTION_FAILURE.json"
OI_JSONL_SHA256 = "c4744a9369844f453476589111c2436372e729e7afdbe5fb34b6e9938a905b94"
OI_JSONL_ROWS = 455273
FIVE_MS = 300_000
END_2025_MS = 1_735_689_600_000


class PreConsumptionBlocker(RuntimeError):
    """Authority or bound-data failure before outcome-bearing evaluation."""


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> str:
    raw = canonical_json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return _sha256_bytes(raw)


def require_armed_head() -> None:
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    if head != ARMED_HEAD or tree != ARMED_TREE:
        raise PreConsumptionBlocker(
            f"MARKET_02_ARM_HEAD_MISMATCH:{head}/{tree}"
        )


def authenticate_pre_execution() -> dict[str, Any]:
    require_armed_head()
    bound = authenticate_market_02_canonical_execution()
    reservation = bound["reservation"]
    if int(reservation["CANONICAL_EXECUTIONS_AUTHORIZED"]) != 1:
        raise PreConsumptionBlocker("MARKET_02_RESERVATION_AUTHORIZED_MISMATCH")
    if int(reservation["CANONICAL_EXECUTIONS_CONSUMED"]) != 0:
        raise PreConsumptionBlocker("MARKET_02_RESERVATION_ALREADY_CONSUMED")
    if MARKET_02_TEST_CALIBRATED is not False:
        raise PreConsumptionBlocker("MARKET_02_TEST_CALIBRATED_MUTATED")
    if B2_06_EXECUTION_AUTHORIZED is not False:
        raise PreConsumptionBlocker("MARKET_02_B2_06_MUTATED")
    if DEFAULT_V4 is not False:
        raise PreConsumptionBlocker("MARKET_02_DEFAULT_V4_MUTATED")
    if PROTECTED_OOS_AUTHORIZED is not False:
        raise PreConsumptionBlocker("MARKET_02_PROTECTED_OOS_MUTATED")
    if bound["run_identity"] != FROZEN_MARKET_02_RUN_IDENTITY:
        raise PreConsumptionBlocker("MARKET_02_RUN_IDENTITY_MISMATCH")
    if str(MARKET_02_BOOTSTRAP_SEED) != "1852983754304692007":
        raise PreConsumptionBlocker("MARKET_02_SEED_MISMATCH")
    lock_path = REPO / LOCK_REL
    if lock_path.exists():
        raise PreConsumptionBlocker("MARKET_02_CONSUMPTION_LOCK_ALREADY_PRESENT")
    result_path = REPO / RESULT_REL
    if result_path.exists():
        raise PreConsumptionBlocker("MARKET_02_RESULT_ALREADY_PRESENT")
    return bound


def _load_core_checksums() -> dict[str, str]:
    payload = json.loads(CORE_SNAPSHOT_DOC.read_text(encoding="utf-8"))
    identity = payload["identity_payload"]
    if identity.get("dataset_id") != PRICE_DATASET_ID:
        raise PreConsumptionBlocker("MARKET_02_CORE_SNAPSHOT_DOC_MISMATCH")
    if sha256_file(CORE_SNAPSHOT_DOC) != CORE_SNAPSHOT_IDENTITY_SHA256:
        raise PreConsumptionBlocker("MARKET_02_CORE_IDENTITY_SHA256_MISMATCH")
    checksums = identity["output_checksums"]
    return {str(k): str(v) for k, v in checksums.items() if isinstance(v, str)}


def load_bound_price() -> tuple[PriceView, dict[str, Any]]:
    if not CORE_ROOT.is_dir():
        raise PreConsumptionBlocker("MARKET_02_CORE_DATASET_MISSING")
    checksums = _load_core_checksums()
    try:
        paths = list_development_parquet_paths(CORE_ROOT)
    except Exception as exc:
        raise PreConsumptionBlocker(f"MARKET_02_CORE_PATHS:{exc}") from exc
    if not paths:
        raise PreConsumptionBlocker("MARKET_02_CORE_NO_DEVELOPMENT_PARQUET")
    authenticated: list[dict[str, str]] = []
    for path in paths:
        rel = f"canonical/1m/monthly/{path.name}"
        expected = checksums.get(rel)
        if expected is None:
            raise PreConsumptionBlocker(f"MARKET_02_CORE_CHECKSUM_UNBOUND:{rel}")
        digest = sha256_file(path)
        if digest != expected:
            raise PreConsumptionBlocker(f"MARKET_02_CORE_CHECKSUM_MISMATCH:{rel}")
        authenticated.append({"path": rel, "sha256": digest})
        if path.name.startswith(("2025-", "2026-")):
            raise PreConsumptionBlocker(f"MARKET_02_CORE_OPENED_FORBIDDEN:{rel}")
    import pyarrow.parquet as pq

    opens, avails, closes = [], [], []
    for path in paths:
        table = pq.read_table(path, columns=["open_time_ms", "available_at_ms", "close"])
        if "close_time_ms" in table.column_names:
            raise PreConsumptionBlocker("MARKET_02_CORE_CLOSE_TIME_LOADED")
        opens.append(np.asarray(table.column("open_time_ms").to_pylist(), dtype=np.int64))
        avails.append(np.asarray(table.column("available_at_ms").to_pylist(), dtype=np.int64))
        closes.append(
            np.array(
                [parse_px(x) for x in table.column("close").to_pylist()],
                dtype=np.float64,
            )
        )
    open_ms = np.concatenate(opens)
    order = np.argsort(open_ms, kind="mergesort")
    open_ms = open_ms[order]
    avail_ms = np.concatenate(avails)[order]
    close = np.concatenate(closes)[order]
    if int(open_ms[-1]) >= END_2025_MS:
        raise PreConsumptionBlocker("MARKET_02_CORE_REACHED_2025")
    if np.any(avail_ms != open_ms + 60_000):
        raise PreConsumptionBlocker("MARKET_02_CORE_AVAILABLE_AT_MISMATCH")
    view = PriceView(
        open_time_ms=open_ms,
        available_at_ms=avail_ms,
        close=close,
        snapshot_id=PRICE_SNAPSHOT_ID,
    )
    meta = {
        "n_rows": int(open_ms.shape[0]),
        "n_partitions": len(authenticated),
        "first_open_time_ms": int(open_ms[0]),
        "last_open_time_ms": int(open_ms[-1]),
        "partition_checksums_authenticated": True,
        "forbidden_2025_2026_opened": False,
    }
    return view, meta


def load_bound_oi() -> tuple[OiView, dict[str, Any]]:
    oi_path = OI_ROOT / "canonical" / "oi.jsonl"
    manifest_path = OI_ROOT / "reports" / "snapshot_manifest.json"
    if not oi_path.is_file():
        raise PreConsumptionBlocker("MARKET_02_OI_JSONL_MISSING")
    if not manifest_path.is_file():
        raise PreConsumptionBlocker("MARKET_02_OI_SNAPSHOT_MANIFEST_MISSING")
    runtime = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime_id = runtime.get("snapshot_id")
    if runtime_id != OI_SNAPSHOT_ID:
        raise PreConsumptionBlocker(
            f"MARKET_02_OI_RUNTIME_SNAPSHOT_MISMATCH:{runtime_id}"
        )
    digest = sha256_file(oi_path)
    if digest != OI_JSONL_SHA256:
        raise PreConsumptionBlocker("MARKET_02_OI_JSONL_SHA256_MISMATCH")
    bound_doc = json.loads(OI_SNAPSHOT_DOC.read_text(encoding="utf-8"))
    if bound_doc.get("snapshot_id") != OI_SNAPSHOT_ID:
        raise PreConsumptionBlocker("MARKET_02_OI_BOUND_DOC_MISMATCH")
    if sha256_file(OI_SNAPSHOT_DOC) != OI_SNAPSHOT_IDENTITY_SHA256:
        raise PreConsumptionBlocker("MARKET_02_OI_IDENTITY_SHA256_MISMATCH")
    creates: list[int] = []
    avails: list[int] = []
    values: list[float] = []
    with oi_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            create = int(row["period_start_ms"])
            available = int(row["available_at_ms"])
            if available != create + FIVE_MS:
                raise PreConsumptionBlocker("MARKET_02_OI_AVAILABLE_AT_RULE_MISMATCH")
            creates.append(create)
            avails.append(available)
            values.append(float(row["sum_open_interest"]))
    if len(creates) != OI_JSONL_ROWS:
        raise PreConsumptionBlocker(f"MARKET_02_OI_ROW_COUNT_MISMATCH:{len(creates)}")
    create_ms = np.asarray(creates, dtype=np.int64)
    avail_ms = np.asarray(avails, dtype=np.int64)
    oi_vals = np.asarray(values, dtype=np.float64)
    if np.any(np.diff(avail_ms) < 0):
        order = np.argsort(avail_ms, kind="mergesort")
        create_ms = create_ms[order]
        avail_ms = avail_ms[order]
        oi_vals = oi_vals[order]
    view = OiView(
        create_time_ms=create_ms,
        available_at_ms=avail_ms,
        sum_open_interest=oi_vals,
        snapshot_id=OI_SNAPSHOT_ID,
    )
    meta = {
        "n_rows": int(create_ms.shape[0]),
        "oi_jsonl_sha256": digest,
        "funding_jsonl_opened": False,
        "runtime_snapshot_id": runtime_id,
        "b2_06_evaluator_enabled": False,
    }
    return view, meta


def write_consumption_lock() -> str:
    payload = {
        "schema": "market_02_oi_expansion_price_confirmation_consumption_lock",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "canonical_run_identity": FROZEN_MARKET_02_RUN_IDENTITY,
        "arm_artifact_sha256": ARM_JSON_SHA256,
        "reservation_sha256_unused": RESERVATION_JSON_SHA256,
        "execution_head": ARMED_HEAD,
        "execution_tree": ARMED_TREE,
        "frozen_implementation_head": FROZEN_IMPLEMENTATION_HEAD,
        "frozen_implementation_tree": FROZEN_IMPLEMENTATION_TREE,
        "CANONICAL_EXECUTIONS_AUTHORIZED": 1,
        "consumption_boundary": "FIRST_OUTCOME_BEARING_EVALUATE_BOUND_MARKET_02",
        "CANONICAL_EXECUTIONS_CONSUMED": 1,
        "MARKET_02_TEST_CALIBRATED": False,
        "PROTECTED_OOS_TOUCHED": False,
        "B2_06_EXECUTION_AUTHORIZED": False,
        "DEFAULT_V4": False,
        "not_a_scientific_result": True,
        "written_at_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return _write_json(REPO / LOCK_REL, payload)


def consume_reservation_and_arm() -> dict[str, str]:
    reservation_path = REPO / RESERVATION_JSON_REL
    arm_path = REPO / ARM_JSON_REL
    reservation = json.loads(reservation_path.read_text(encoding="utf-8"))
    arm = json.loads(arm_path.read_text(encoding="utf-8"))
    reservation["CANONICAL_EXECUTIONS_CONSUMED"] = 1
    reservation["MARKET_02_EXECUTED"] = True
    reservation["MARKET_02_OUTCOME_INSPECTED"] = True
    reservation["status"] = "CONSUMED"
    reservation["lifecycle"] = "CONSUMED"
    reservation["one_shot"] = True
    reservation["rerun_preauthorized"] = False
    reservation["replacement_reservation_preauthorized"] = False
    arm["authorization_consumed"] = True
    arm["MARKET_02_EXECUTED"] = True
    arm["MARKET_02_OUTCOME_INSPECTED"] = True
    arm["status"] = "EXECUTED"
    arm["lifecycle"] = "CONSUMED_EXECUTED"
    consumed_reservation_sha = _write_json(reservation_path, reservation)
    consumed_arm_sha = _write_json(arm_path, arm)
    return {
        "reservation_sha256_consumed": consumed_reservation_sha,
        "arm_sha256_consumed": consumed_arm_sha,
    }


def bind_canonical_result(
    scientific: Mapping[str, Any],
    *,
    lock_sha256: str,
    price_meta: Mapping[str, Any],
    oi_meta: Mapping[str, Any],
    consumed: Mapping[str, str],
) -> dict[str, Any]:
    support = scientific.get("support") or {}
    robustness = scientific.get("robustness")
    diagnostics = scientific.get("diagnostics") or {}
    episode = scientific.get("episode_diagnostics") or {}
    return {
        "schema": "market_02_oi_expansion_price_confirmation_canonical_result",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "MARKET_02_PHASE": "RESULT",
        "status": "CANONICAL_RESULT",
        "canonical_run_identity": FROZEN_MARKET_02_RUN_IDENTITY,
        "arm_artifact_sha256_unused": ARM_JSON_SHA256,
        "reservation_sha256_unused": RESERVATION_JSON_SHA256,
        "arm_sha256_consumed": consumed["arm_sha256_consumed"],
        "reservation_sha256_consumed": consumed["reservation_sha256_consumed"],
        "consumption_lock_sha256": lock_sha256,
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "implementation_freeze_json_sha256": IMPL_FREEZE_JSON_SHA256,
        "lib_reviewed_sha256": LIB_REVIEWED_SHA256,
        "lib_armed_lifecycle_sha256": LIB_ARMED_LIFECYCLE_SHA256,
        "b2_03_sha256": B2_03_SHA256,
        "v1_lib_sha256": V1_LIB_SHA256,
        "v3_selector_module_sha256": V3_SELECTOR_MODULE_SHA256,
        "execution_head": ARMED_HEAD,
        "execution_tree": ARMED_TREE,
        "frozen_implementation_head": FROZEN_IMPLEMENTATION_HEAD,
        "frozen_implementation_tree": FROZEN_IMPLEMENTATION_TREE,
        "price_dataset_id": PRICE_DATASET_ID,
        "price_snapshot_id": PRICE_SNAPSHOT_ID,
        "price_identity_sha256": CORE_SNAPSHOT_IDENTITY_SHA256,
        "oi_snapshot_id": OI_SNAPSHOT_ID,
        "oi_identity_sha256": OI_SNAPSHOT_IDENTITY_SHA256,
        "common_start_inclusive": COMMON_START_INCLUSIVE,
        "common_end_exclusive": COMMON_END_EXCLUSIVE,
        "price_load": dict(price_meta),
        "oi_load": dict(oi_meta),
        "MARKET_02_BOOTSTRAP_SEED": MARKET_02_BOOTSTRAP_SEED,
        "json_twin_stored_numeric": "1852983754304692000",
        "seed_material": SEED_MATERIAL,
        "seed_material_sha256": SEED_MATERIAL_SHA256,
        "CANONICAL_EXECUTIONS_AUTHORIZED": CANONICAL_EXECUTIONS_AUTHORIZED,
        "CANONICAL_EXECUTIONS_CONSUMED": 1,
        "MARKET_02_ARMED": True,
        "MARKET_02_EXECUTED": True,
        "MARKET_02_OUTCOME_INSPECTED": True,
        "MARKET_02_TEST_CALIBRATED": False,
        "PROTECTED_OOS_AUTHORIZED": False,
        "PROTECTED_OOS_TOUCHED": False,
        "B2_06_EXECUTION_AUTHORIZED": False,
        "DEFAULT_V4": False,
        "v3_reused_as_market_02_test": False,
        "funding_in_scope": False,
        "rerun_occurred": False,
        "scientific_result": dict(scientific),
        "TOTAL_ELIGIBLE_EPISODES": support.get("TOTAL_ELIGIBLE_EPISODES"),
        "CANDIDATE_EPISODES": support.get("CANDIDATE_EPISODES"),
        "BASELINE_EPISODES": support.get("BASELINE_EPISODES"),
        "USABLE_STRATA": support.get("USABLE_STRATA"),
        "usable_stratum_ids": support.get("usable_stratum_ids"),
        "eligible_exclusion_counts": episode.get("exclusion_counts"),
        "stratum_counts": diagnostics.get("stratum_counts"),
        "beta_confirmation": scientific.get("beta_confirmation"),
        "se_hat": scientific.get("se_hat"),
        "p_one_sided": scientific.get("p_one_sided"),
        "detected": scientific.get("detected"),
        "bootstrap": scientific.get("bootstrap"),
        "robustness": None if robustness is None else dict(robustness),
        "final_classification": scientific.get("final_classification"),
    }


def seal_result(payload: Mapping[str, Any]) -> str:
    text = dumps_result(payload)
    if not text.endswith("\n"):
        text = text + "\n"
    raw = text.encode("utf-8")
    path = REPO / RESULT_REL
    path.write_bytes(raw)
    digest = _sha256_bytes(raw)
    sidecar = path.with_suffix(".json.sha256")
    sidecar.write_text(digest + "\n", encoding="utf-8")
    return digest


def write_post_consumption_failure(exc: BaseException, lock_sha256: str | None) -> str:
    payload = {
        "schema": "market_02_oi_expansion_price_confirmation_execution_failure",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "canonical_run_identity": FROZEN_MARKET_02_RUN_IDENTITY,
        "consumption_lock_sha256": lock_sha256,
        "CANONICAL_EXECUTIONS_CONSUMED": 1,
        "rerun_occurred": False,
        "MARKET_02_TEST_CALIBRATED": False,
        "PROTECTED_OOS_TOUCHED": False,
        "B2_06_EXECUTION_AUTHORIZED": False,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(),
        "adjudication_required": True,
    }
    return _write_json(REPO / FAILURE_REL, payload)


def main(argv: list[str] | None = None) -> int:
    if argv:
        print(
            "caller arguments cannot redefine MARKET-02 scientific authority",
            file=sys.stderr,
        )
        return 2
    try:
        authenticate_pre_execution()
        print("PRE_EXECUTION_AUTH_OK", file=sys.stderr)
        price, price_meta = load_bound_price()
        print("BOUND_PRICE_AUTH_OK", file=sys.stderr)
        oi, oi_meta = load_bound_oi()
        print("BOUND_OI_AUTH_OK", file=sys.stderr)
    except PreConsumptionBlocker as exc:
        print(f"PRE_CONSUMPTION_BLOCKER:{exc}", file=sys.stderr)
        return 3

    lock_sha256 = write_consumption_lock()
    print(f"CONSUMPTION_BOUNDARY_ENTERED lock_sha256={lock_sha256}", file=sys.stderr)
    scientific: dict[str, Any] | None = None
    post_exc: BaseException | None = None
    try:
        scientific = evaluate_bound_market_02(price, oi)
    except BaseException as exc:  # noqa: BLE001 - consume even on failure
        post_exc = exc
    consumed = consume_reservation_and_arm()
    print("RESERVATION_CONSUMED", file=sys.stderr)
    if post_exc is not None:
        failure_sha = write_post_consumption_failure(post_exc, lock_sha256)
        print(f"POST_CONSUMPTION_FAILURE sha256={failure_sha}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 4
    assert scientific is not None
    package = bind_canonical_result(
        scientific,
        lock_sha256=lock_sha256,
        price_meta=price_meta,
        oi_meta=oi_meta,
        consumed=consumed,
    )
    result_sha = seal_result(package)
    replay = dumps_result(package)
    if not replay.endswith("\n"):
        replay = replay + "\n"
    if _sha256_bytes(replay.encode("utf-8")) != result_sha:
        print("RESULT_SERIALIZATION_MISMATCH", file=sys.stderr)
        return 4
    print(f"RESULT_SEALED path={RESULT_REL} sha256={result_sha}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
