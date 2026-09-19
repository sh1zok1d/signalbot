"""MARKET-05 post-claim scientific execution.

This module is imported only AFTER the atomic execution claim exists.
It contains no scientific math: it loads bound OHLC, calls the frozen
evaluator, and writes RESULT. Claim already consumed the one-shot.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

BTC_DATASET_ROOT_REL = "artifacts/research_data/CORE_BTC_BINANCE_V0"
ETH_DATASET_ROOT_REL = "artifacts/research_data/CORE_ETH_BINANCE_V0"


class Market05IncompleteExecution(RuntimeError):
    """A predeclared integrity condition from the frozen prereg."""


class Market05CanonicalExecutionError(RuntimeError):
    """Post-claim execution / RESULT failure."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _path(rel: str) -> Path:
    return _repo_root() / rel


def verify_imported_module_paths() -> None:
    import scripts.research.market05_cross_asset_canonical_execution as self_mod
    import scripts.research.market05_cross_asset_lib as lib

    expected_self = (_repo_root() / "scripts/research/market05_cross_asset_canonical_execution.py").resolve()
    expected_lib = (_repo_root() / "scripts/research/market05_cross_asset_lib.py").resolve()
    actual_self = Path(self_mod.__file__).resolve()
    actual_lib = Path(lib.__file__).resolve()
    if actual_self != expected_self:
        raise Market05CanonicalExecutionError(
            f"MARKET_05_IMPORTED_EXECUTION_PATH_MISMATCH:{actual_self}"
        )
    if actual_lib != expected_lib:
        raise Market05CanonicalExecutionError(
            f"MARKET_05_IMPORTED_LIB_PATH_MISMATCH:{actual_lib}"
        )


def verify_imported_lib_path(lib_file: str) -> None:
    expected = (_repo_root() / "scripts/research/market05_cross_asset_lib.py").resolve()
    if Path(lib_file).resolve() != expected:
        raise Market05CanonicalExecutionError(
            f"MARKET_05_IMPORTED_LIB_PATH_MISMATCH:{lib_file}"
        )


def _read_bars(paths: Sequence[Path], *, dataset_id: str) -> dict[int, Any]:
    """Read 1m bars: open_time_ms, high, low, close. Never close-as-high/low."""
    import pyarrow.parquet as pq

    from scripts.research.market05_cross_asset_lib import Bar, PROTECTED_OOS_START_MS
    from scripts.research.market05_cross_asset_arm_authority import Market05ArmAuthorityError

    bars: dict[int, Any] = {}
    for path in paths:
        table = pq.read_table(path, columns=["open_time_ms", "high", "low", "close"])
        missing = [
            col
            for col in ("open_time_ms", "high", "low", "close")
            if col not in table.column_names
        ]
        if missing:
            raise Market05IncompleteExecution(
                f"MARKET_05_PARQUET_COLUMNS_MISSING:{dataset_id}:{missing}"
            )
        opens = table.column("open_time_ms").to_pylist()
        highs = table.column("high").to_pylist()
        lows = table.column("low").to_pylist()
        closes = table.column("close").to_pylist()
        for open_ms, high, low, close in zip(opens, highs, lows, closes):
            open_ms = int(open_ms)
            if open_ms >= PROTECTED_OOS_START_MS:
                raise Market05ArmAuthorityError("MARKET_05_PROTECTED_OOS_ROW_REFUSED")
            bars[open_ms] = Bar(
                open_time_ms=open_ms,
                high=float(high),
                low=float(low),
                close=float(close),
            )
    return bars


def load_bound_development_rows_after_claim() -> tuple[list[Any], dict[str, int]]:
    """Load CORE rows. Must only be called after the execution claim exists."""
    from scripts.research.market05_cross_asset_data_preflight import (
        btc_development_parquet_rels,
        sha256_file,
    )
    from scripts.research.market05_cross_asset_execution_claim import claim_exists
    from scripts.research.market05_cross_asset_lib import (
        EligibleRow,
        PROTECTED_OOS_START_MS,
        build_eligible_row,
        feature_open_times,
        outcome_open_times,
        prefix_open_time,
    )
    from scripts.research.market05_cross_asset_arm_authority import (
        BTC_DATASET_ID,
        BTC_SNAPSHOT_DOC_REL,
        ETH_DATASET_ID,
        Market05CanonicalExecutionNotAuthorized,
    )
    from scripts.research.market05_eth_execution_binding import load_execution_binding

    if not claim_exists():
        raise Market05CanonicalExecutionNotAuthorized(
            "MARKET_05_SCIENCE_REQUIRES_EXECUTION_CLAIM"
        )

    btc_snapshot = json.loads(_path(BTC_SNAPSHOT_DOC_REL).read_text(encoding="utf-8"))
    btc_checksums = (btc_snapshot.get("identity_payload") or btc_snapshot).get(
        "output_checksums"
    ) or {}
    btc_rels = btc_development_parquet_rels(btc_snapshot)
    btc_root = _path(BTC_DATASET_ROOT_REL)
    btc_paths = []
    for rel in btc_rels:
        path = btc_root / rel
        if sha256_file(path) != btc_checksums[rel]:
            raise Market05CanonicalExecutionError(
                f"MARKET_05_CORE_CHECKSUM_MISMATCH:BTC:{rel}"
            )
        btc_paths.append(path)

    eth_binding = load_execution_binding(_repo_root())
    eth_root = _path(ETH_DATASET_ROOT_REL)
    eth_paths = []
    for obj in eth_binding["objects"]:
        rel = obj["canonical_parquet_relative_path"]
        path = eth_root / rel
        if sha256_file(path) != obj["canonical_parquet_sha256"]:
            raise Market05CanonicalExecutionError(
                f"MARKET_05_CORE_CHECKSUM_MISMATCH:ETH:{rel}"
            )
        eth_paths.append(path)

    btc_bars = _read_bars(btc_paths, dataset_id=BTC_DATASET_ID)
    eth_bars = _read_bars(eth_paths, dataset_id=ETH_DATASET_ID)

    rows: list[EligibleRow] = []
    n_candidates = 0
    n_missing_prefix = 0
    n_ineligible = 0
    decision_times = sorted(
        t
        for t in btc_bars
        if t % 86_400_000 == 0 and t + 86_400_000 <= PROTECTED_OOS_START_MS
    )
    for t_ms in decision_times:
        n_candidates += 1
        btc_window = [btc_bars[o] for o in feature_open_times(t_ms) if o in btc_bars]
        eth_window = [eth_bars[o] for o in feature_open_times(t_ms) if o in eth_bars]
        btc_out = [btc_bars[o] for o in outcome_open_times(t_ms) if o in btc_bars]
        btc_prefix = btc_bars.get(prefix_open_time(t_ms))
        eth_prefix = eth_bars.get(prefix_open_time(t_ms))
        if btc_prefix is None or eth_prefix is None:
            n_missing_prefix += 1
            continue
        row = build_eligible_row(
            t_ms, btc_window + btc_out, btc_prefix, eth_window, eth_prefix
        )
        if row is None:
            n_ineligible += 1
            continue
        rows.append(row)
    if not rows:
        raise Market05IncompleteExecution("MARKET_05_NO_ELIGIBLE_ROWS")
    exclusions = {
        "decision_candidates": n_candidates,
        "missing_prefix": n_missing_prefix,
        "ineligible_after_same_support": n_ineligible,
        "eligible_rows": len(rows),
    }
    return rows, exclusions


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(str(directory), flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_result_json_atomically(path: Path, data: bytes) -> None:
    if path.exists():
        raise Market05CanonicalExecutionError("MARKET_05_RESULT_ALREADY_PRESENT")
    tmp = path.with_name(path.name + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(tmp), flags, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))
    _fsync_directory(path.parent)


def _result_markdown(payload: Mapping[str, Any]) -> str:
    maes = payload.get("maes") or {}
    coef = payload.get("coefficients") or {}
    lines = [
        "# MARKET-05 CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK — RESULT",
        "",
        f"- research_id: `{payload['research_id']}`",
        f"- run_identity: `{payload['run_identity']}`",
        f"- result_status: `{payload.get('result_status')}`",
        f"- classification: **{payload['classification']}**",
        f"- POOLED_MAE_BASELINE: `{maes.get('POOLED_MAE_BASELINE')}`",
        f"- POOLED_MAE_CANDIDATE: `{maes.get('POOLED_MAE_CANDIDATE')}`",
        f"- RELATIVE_MAE_IMPROVEMENT: `{maes.get('RELATIVE_MAE_IMPROVEMENT')}`",
        f"- BETA_ETH_CONFIRMATION: `{coef.get('BETA_ETH_CONFIRMATION')}`",
        "",
        "Canonical scientific evidence is `MARKET_05_RESULT.json`.",
        "This markdown is a human-readable rendering of that JSON.",
        "",
    ]
    return "\n".join(lines)


def required_complete_result_paths(payload: Mapping[str, Any]) -> list[str]:
    from scripts.research.market05_cross_asset_lib import (
        required_complete_result_paths as _required,
    )

    return _required(payload)


def _assemble_result_payload(
    evaluation: Mapping[str, Any],
    *,
    run_identity: str,
    exclusions: Mapping[str, int],
    env: Mapping[str, Any],
    claim_sha256: str,
    arm_sha256: str,
    reservation_sha256: str,
) -> dict[str, Any]:
    from scripts.research.market05_cross_asset_arm_authority import (
        BTC_DATASET_ID,
        BTC_SNAPSHOT_ID,
        ETH_DATASET_ID,
        ETH_EXECUTION_DATA_ID,
        ETH_SNAPSHOT_ID,
        FROZEN_PREREG_JSON_SHA256,
        FROZEN_PREREG_MD_SHA256,
        RESEARCH_ID,
        RESULT_SCHEMA_IDENTITY,
        SCIENTIFIC_IMPLEMENTATION_HASHES,
    )
    from scripts.research.market05_cross_asset_authority_root import (
        SCIENTIFIC_IMPLEMENTATION_HEAD,
        SCIENTIFIC_IMPLEMENTATION_TREE,
    )
    from scripts.research.market05_cross_asset_lib import (
        CLASS_INCOMPLETE,
        RESULT_SCHEMA_KEYS,
    )

    year_rel = evaluation.get("YEAR_RELATIVE_MAE_IMPROVEMENT") or {}
    year_metrics = {int(k): v for k, v in year_rel.items()}
    folds = evaluation.get("folds") or []
    fold_counts = {
        str(item.get("name")): {
            "train_n": item.get("train_n"),
            "test_n": item.get("test_n"),
            "MAE_BASELINE": item.get("MAE_BASELINE"),
            "MAE_CANDIDATE": item.get("MAE_CANDIDATE"),
        }
        for item in folds
    }
    payload: dict[str, Any] = {key: None for key in RESULT_SCHEMA_KEYS}
    payload.update(
        {
            "research_id": RESEARCH_ID,
            "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
            "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
            "implementation_head": SCIENTIFIC_IMPLEMENTATION_HEAD,
            "implementation_tree": SCIENTIFIC_IMPLEMENTATION_TREE,
            "scientific_implementation_hashes": dict(
                sorted(SCIENTIFIC_IMPLEMENTATION_HASHES.items())
            ),
            "btc_dataset_id": BTC_DATASET_ID,
            "btc_snapshot_id": BTC_SNAPSHOT_ID,
            "eth_dataset_id": ETH_DATASET_ID,
            "eth_snapshot_id": ETH_SNAPSHOT_ID,
            "eth_execution_data_id": ETH_EXECUTION_DATA_ID,
            "run_identity": run_identity,
            "execution_claim_sha256": claim_sha256,
            "arm_sha256": arm_sha256,
            "reservation_sha256": reservation_sha256,
            "protected_oos_touched": False,
            "scientific_consumed": True,
            "result_status": "COMPLETE",
            "result_schema_identity": RESULT_SCHEMA_IDENTITY,
            "numpy_version": env.get("numpy_version"),
            "pyarrow_version": env.get("pyarrow_version"),
            "python_version": env.get("python_version"),
            "python_implementation": env.get("python_implementation"),
            "git_executable": env.get("git_executable"),
            "git_version": env.get("git_version"),
            "row_counts": evaluation.get("row_counts")
            or {"eligible_rows": exclusions.get("eligible_rows")},
            "exclusion_counts": dict(exclusions),
            "fold_counts": fold_counts,
            "folds": folds,
            "coefficients": {
                "BETA_ETH_CONFIRMATION": evaluation.get("BETA_ETH_CONFIRMATION")
            },
            "bootstrap": {
                "kind": evaluation.get("bootstrap_kind"),
                "block_length": evaluation.get("bootstrap_block_length"),
                "replicates_predictive": evaluation.get("bootstrap_replicates_predictive"),
                "replicates_coefficient": evaluation.get("bootstrap_replicates_coefficient"),
                "random_seed": evaluation.get("random_seed"),
                "predictive_bootstrap_refit": evaluation.get("predictive_bootstrap_refit"),
                "coefficient_bootstrap_refit": evaluation.get("coefficient_bootstrap_refit"),
            },
            "bootstrap_cis": {
                "BETA_ETH_CONFIRMATION_CI": evaluation.get("BETA_ETH_CONFIRMATION_CI"),
                "RELATIVE_MAE_IMPROVEMENT_CI": evaluation.get("RELATIVE_MAE_IMPROVEMENT_CI"),
            },
            "maes": {
                "POOLED_MAE_BASELINE": evaluation.get("POOLED_MAE_BASELINE"),
                "POOLED_MAE_CANDIDATE": evaluation.get("POOLED_MAE_CANDIDATE"),
                "RELATIVE_MAE_IMPROVEMENT": evaluation.get("RELATIVE_MAE_IMPROVEMENT"),
            },
            "year_metrics": year_metrics,
            "gates": evaluation.get("gates"),
            "classification": evaluation.get("classification") or CLASS_INCOMPLETE,
        }
    )
    return payload


def execute_science_after_claim() -> dict[str, Any]:
    """Evaluate and write RESULT. Claim already exists; never reruns if it does."""
    from scripts.research.market05_cross_asset_arm_authority import (
        ARM_JSON_REL,
        RESULT_JSON_REL,
        RESULT_MD_REL,
        RESERVATION_JSON_REL,
        canonical_json_bytes,
        execution_environment_record,
        sha256_file,
    )
    from scripts.research.market05_cross_asset_execution_claim import (
        Market05ExecutionClaimError,
        claim_exists,
        load_execution_claim,
        sha256_claim_file,
        update_claim_result_status,
    )
    from scripts.research.market05_cross_asset_lib import (
        CLASS_INCOMPLETE,
        evaluate_prepared_rows,
        instantiate_scientific_result,
    )

    if not claim_exists():
        raise Market05CanonicalExecutionError("MARKET_05_SCIENCE_REQUIRES_EXECUTION_CLAIM")
    claim = load_execution_claim()
    run_identity = str(claim["run_identity"])

    json_path = _path(RESULT_JSON_REL)
    md_path = _path(RESULT_MD_REL)
    if json_path.exists():
        raise Market05CanonicalExecutionError("MARKET_05_RESULT_ALREADY_PRESENT")

    try:
        rows, exclusions = load_bound_development_rows_after_claim()
        evaluation = evaluate_prepared_rows(rows)
        env = execution_environment_record()
        payload = _assemble_result_payload(
            evaluation,
            run_identity=run_identity,
            exclusions=exclusions,
            env=env,
            claim_sha256=sha256_claim_file(),
            arm_sha256=sha256_file(_path(ARM_JSON_REL)),
            reservation_sha256=sha256_file(_path(RESERVATION_JSON_REL)),
        )
        missing = required_complete_result_paths(payload)
        if missing:
            raise Market05IncompleteExecution(
                "MARKET_05_RESULT_NUMERIC_EVIDENCE_INCOMPLETE:" + ",".join(missing)
            )
        result = instantiate_scientific_result(payload)
        write_result_json_atomically(json_path, canonical_json_bytes(result))
        try:
            md_path.write_text(_result_markdown(result), encoding="utf-8")
        except OSError:
            update_claim_result_status("COMPLETE_JSON_MD_INCOMPLETE")
            return {
                "run_identity": run_identity,
                "result_status": "COMPLETE_JSON_MD_INCOMPLETE",
                "classification": result["classification"],
            }
        try:
            update_claim_result_status("COMPLETE")
        except Market05ExecutionClaimError:
            pass
        return {
            "run_identity": run_identity,
            "result_status": "COMPLETE",
            "classification": result["classification"],
            "CANONICAL_EXECUTIONS_CONSUMED": "1",
        }
    except Exception:
        try:
            if not json_path.exists():
                update_claim_result_status("INCOMPLETE_OR_UNKNOWN")
        except Exception:
            pass
        raise


def execute_synthetic_after_claim(
    rows: Sequence[Any],
    *,
    predictive_replicates: int = 8,
    coefficient_replicates: int = 8,
) -> dict[str, Any]:
    """Test/helper: evaluate caller-supplied rows after a claim exists.

    Does not load CORE datasets. Still refuses without a claim and still
    cannot overwrite RESULT.
    """
    from scripts.research.market05_cross_asset_arm_authority import (
        ARM_JSON_REL,
        RESULT_JSON_REL,
        RESULT_MD_REL,
        RESERVATION_JSON_REL,
        canonical_json_bytes,
        execution_environment_record,
        sha256_file,
    )
    from scripts.research.market05_cross_asset_execution_claim import (
        claim_exists,
        load_execution_claim,
        sha256_claim_file,
        update_claim_result_status,
    )
    from scripts.research.market05_cross_asset_lib import (
        evaluate_prepared_rows,
        instantiate_scientific_result,
    )

    if not claim_exists():
        raise Market05CanonicalExecutionError("MARKET_05_SCIENCE_REQUIRES_EXECUTION_CLAIM")
    claim = load_execution_claim()
    json_path = _path(RESULT_JSON_REL)
    if json_path.exists():
        raise Market05CanonicalExecutionError("MARKET_05_RESULT_ALREADY_PRESENT")
    evaluation = evaluate_prepared_rows(
        rows,
        predictive_replicates=predictive_replicates,
        coefficient_replicates=coefficient_replicates,
    )
    payload = _assemble_result_payload(
        evaluation,
        run_identity=str(claim["run_identity"]),
        exclusions={"eligible_rows": len(rows), "synthetic": 1},
        env=execution_environment_record(),
        claim_sha256=sha256_claim_file(),
        arm_sha256=sha256_file(_path(ARM_JSON_REL)),
        reservation_sha256=sha256_file(_path(RESERVATION_JSON_REL)),
    )
    missing = required_complete_result_paths(payload)
    if missing:
        raise Market05IncompleteExecution(
            "MARKET_05_RESULT_NUMERIC_EVIDENCE_INCOMPLETE:" + ",".join(missing)
        )
    result = instantiate_scientific_result(payload)
    write_result_json_atomically(json_path, canonical_json_bytes(result))
    _path(RESULT_MD_REL).write_text(_result_markdown(result), encoding="utf-8")
    update_claim_result_status("COMPLETE")
    return result


def load_bound_development_rows() -> list[Any]:
    """Compatibility wrapper: root first, then claim, then rows."""
    from scripts.research.market05_cross_asset_authority_root import (
        verify_authority_root,
    )

    verify_authority_root()
    rows, _exclusions = load_bound_development_rows_after_claim()
    return rows


def run_canonical_market_05_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Deprecated name. Production callers must use the bootstrap.

    Kept so existing tests that monkeypatch this symbol still have a hook,
    but this function refuses if scientific modules were the first entry.
    Use ``run_canonical_market_05_bootstrap``.
    """
    if args or kwargs:
        raise Market05CanonicalExecutionError(
            "caller arguments cannot redefine MARKET-05 canonical execution"
        )
    from scripts.research.market05_cross_asset_bootstrap import (
        run_canonical_market_05_bootstrap,
    )

    return run_canonical_market_05_bootstrap()
