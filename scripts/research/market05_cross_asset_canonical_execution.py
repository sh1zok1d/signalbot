"""MARKET-05 canonical execution driver.

Exactly one authorized canonical execution:

    authenticate ARM + RESERVATION
      -> load bound CORE development rows (checksum-authenticated)
      -> evaluate with the FROZEN evaluator (no math defined here)
      -> write RESULT to the predeclared paths only
      -> consume the authorization durably

This module contains no scientific math. Feature construction, outcome
construction, folds, standardization, regression, the bootstrap statistic
and classification all remain in the frozen
``market05_cross_asset_lib.py`` and are called, never reimplemented.

Before ARM every entry point here refuses. The refusal is a lifecycle
state, not a property of the code: the same bytes become authorized once
an authenticated ARM + RESERVATION pair exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.research.market05_cross_asset_arm_authority import (
    BTC_DATASET_ID,
    BTC_SNAPSHOT_DOC_REL,
    BTC_SNAPSHOT_ID,
    ETH_DATASET_ID,
    ETH_SNAPSHOT_DOC_REL,
    ETH_SNAPSHOT_ID,
    RESULT_JSON_REL,
    RESULT_MD_REL,
    Market05ArmAuthorityError,
    Market05CanonicalExecutionNotAuthorized,
    SCIENTIFIC_IMPLEMENTATION_HASHES,
    _repo_root,
    authenticate_market_05_canonical_execution,
    canonical_json_bytes,
    consume_authorization_atomically,
    derive_market_05_run_identity,
    sha256_file,
)
from scripts.research.market05_cross_asset_lib import (
    Bar,
    CLASS_INCOMPLETE,
    EligibleRow,
    PROTECTED_OOS_START_MS,
    RESULT_SCHEMA_KEYS,
    build_eligible_row,
    evaluate_prepared_rows,
    feature_open_times,
    instantiate_scientific_result,
    outcome_open_times,
    prefix_open_time,
)

BTC_DATASET_ROOT_REL = "artifacts/research_data/CORE_BTC_BINANCE_V0"
ETH_DATASET_ROOT_REL = "artifacts/research_data/CORE_ETH_BINANCE_V0"

# Filenames whose period lies at or beyond the protected boundary are
# refused outright; a development execution never opens them.
PROTECTED_FILENAME_PREFIXES = ("2025-", "2026-", "2027-")


class Market05IncompleteExecution(RuntimeError):
    """A predeclared integrity condition from the frozen prereg.

    Maps to MARKET_05_INCOMPLETE_EXECUTION, never to NO_EVIDENCE and never
    to a promotion.
    """


def _path(rel: str) -> Path:
    return _repo_root() / rel


def _load_snapshot_checksums(rel: str, dataset_id: str, snapshot_id: str) -> dict[str, str]:
    """Bind a dataset's per-object checksum map from its accepted snapshot doc."""
    path = _path(rel)
    if path.is_symlink():
        raise Market05ArmAuthorityError(f"MARKET_05_SNAPSHOT_DOC_SYMLINK_REFUSED:{rel}")
    if not path.is_file():
        raise Market05IncompleteExecution(f"MARKET_05_SNAPSHOT_DOC_MISSING:{rel}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("snapshot_id") != snapshot_id:
        raise Market05ArmAuthorityError(f"MARKET_05_SNAPSHOT_ID_MISMATCH:{dataset_id}")
    identity = payload.get("identity_payload") or payload
    if identity.get("dataset_id") != dataset_id:
        raise Market05ArmAuthorityError(f"MARKET_05_DATASET_ID_MISMATCH:{dataset_id}")
    checksums = identity.get("output_checksums") or {}
    return {str(k): str(v) for k, v in checksums.items() if isinstance(v, str)}


def _authenticated_development_parquet_paths(
    root_rel: str, checksums: Mapping[str, str], dataset_id: str
) -> list[Path]:
    """Enumerate development 1m parquet objects, checksum-verified.

    Any object whose period is at or beyond the protected boundary is
    refused -- the whole execution fails rather than silently skipping it.
    """
    root = _path(root_rel)
    if not root.is_dir():
        raise Market05IncompleteExecution(f"MARKET_05_CORE_DATASET_MISSING:{dataset_id}")
    candidates = sorted(root.glob("canonical/1m/**/*.parquet"))
    if not candidates:
        raise Market05IncompleteExecution(
            f"MARKET_05_CORE_NO_DEVELOPMENT_PARQUET:{dataset_id}"
        )
    selected: list[Path] = []
    for path in candidates:
        if path.is_symlink():
            raise Market05ArmAuthorityError(
                f"MARKET_05_DATASET_SYMLINK_REFUSED:{path.name}"
            )
        if path.name.startswith(PROTECTED_FILENAME_PREFIXES):
            raise Market05ArmAuthorityError(
                f"MARKET_05_PROTECTED_OOS_OBJECT_REFUSED:{dataset_id}:{path.name}"
            )
        rel = path.relative_to(root).as_posix()
        expected = checksums.get(rel)
        if expected is None:
            raise Market05ArmAuthorityError(
                f"MARKET_05_CORE_CHECKSUM_UNBOUND:{dataset_id}:{rel}"
            )
        if sha256_file(path) != expected:
            raise Market05ArmAuthorityError(
                f"MARKET_05_CORE_CHECKSUM_MISMATCH:{dataset_id}:{rel}"
            )
        selected.append(path)
    return selected


def _read_bars(paths: Sequence[Path]) -> dict[int, Bar]:
    """Read 1m bars under the frozen bar-end-exclusive contract."""
    import pyarrow.parquet as pq

    bars: dict[int, Bar] = {}
    for path in paths:
        table = pq.read_table(path, columns=["open_time_ms", "close"])
        opens = table.column("open_time_ms").to_pylist()
        closes = table.column("close").to_pylist()
        for open_ms, close in zip(opens, closes):
            open_ms = int(open_ms)
            if open_ms >= PROTECTED_OOS_START_MS:
                raise Market05ArmAuthorityError("MARKET_05_PROTECTED_OOS_ROW_REFUSED")
            bars[open_ms] = Bar(open_time_ms=open_ms, close=float(close))
    return bars


def load_bound_development_rows() -> list[EligibleRow]:
    """Authorized CORE row load. Refuses unless ARM authorizes.

    Dataset roots and snapshot identity come from frozen authority, never
    from a caller, so no alternate data path can be substituted.

    The independent authority root is verified BEFORE the ARM authority is
    invoked, so a mutation of the ARM-authority module itself is refused
    before any scientific data is opened.
    """
    from scripts.research.market05_cross_asset_authority_root import (
        verify_authority_root,
    )

    verify_authority_root()
    authenticate_market_05_canonical_execution()

    btc_checksums = _load_snapshot_checksums(
        BTC_SNAPSHOT_DOC_REL, BTC_DATASET_ID, BTC_SNAPSHOT_ID
    )
    eth_checksums = _load_snapshot_checksums(
        ETH_SNAPSHOT_DOC_REL, ETH_DATASET_ID, ETH_SNAPSHOT_ID
    )
    btc_paths = _authenticated_development_parquet_paths(
        BTC_DATASET_ROOT_REL, btc_checksums, BTC_DATASET_ID
    )
    eth_paths = _authenticated_development_parquet_paths(
        ETH_DATASET_ROOT_REL, eth_checksums, ETH_DATASET_ID
    )
    btc_bars = _read_bars(btc_paths)
    eth_bars = _read_bars(eth_paths)

    rows: list[EligibleRow] = []
    decision_times = sorted(
        t
        for t in btc_bars
        if t % 86_400_000 == 0 and t + 86_400_000 <= PROTECTED_OOS_START_MS
    )
    for t_ms in decision_times:
        btc_window = [btc_bars[o] for o in feature_open_times(t_ms) if o in btc_bars]
        eth_window = [eth_bars[o] for o in feature_open_times(t_ms) if o in eth_bars]
        btc_out = [btc_bars[o] for o in outcome_open_times(t_ms) if o in btc_bars]
        btc_prefix = btc_bars.get(prefix_open_time(t_ms))
        eth_prefix = eth_bars.get(prefix_open_time(t_ms))
        if btc_prefix is None or eth_prefix is None:
            continue
        row = build_eligible_row(
            t_ms, btc_window + btc_out, btc_prefix, eth_window, eth_prefix
        )
        if row is not None:
            rows.append(row)
    if not rows:
        raise Market05IncompleteExecution("MARKET_05_NO_ELIGIBLE_ROWS")
    return rows


def _result_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# MARKET-05 CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK — RESULT",
        "",
        f"- research_id: `{payload['research_id']}`",
        f"- run_identity: `{payload['run_identity']}`",
        f"- classification: **{payload['classification']}**",
        "",
        "Machine-readable twin: `MARKET_05_RESULT.json`.",
        "",
    ]
    return "\n".join(lines)


def run_canonical_market_05_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """The one authorized canonical execution. Refuses before ARM."""
    if args or kwargs:
        raise Market05CanonicalExecutionNotAuthorized(
            "caller arguments cannot redefine MARKET-05 canonical execution"
        )
    from scripts.research.market05_cross_asset_authority_root import (
        verify_authority_root,
    )

    verify_authority_root()
    bound = authenticate_market_05_canonical_execution()
    run_identity = bound["run_identity"]
    if run_identity != derive_market_05_run_identity():
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_RUN_IDENTITY_DRIFT")

    rows = load_bound_development_rows()
    evaluation = evaluate_prepared_rows(rows)

    payload = _assemble_result_payload(evaluation, run_identity)
    result = instantiate_scientific_result(payload)

    json_path = _path(RESULT_JSON_REL)
    md_path = _path(RESULT_MD_REL)
    if json_path.exists() or md_path.exists():
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_RESULT_ALREADY_PRESENT")
    json_path.write_bytes(canonical_json_bytes(result))
    md_path.write_text(_result_markdown(result), encoding="utf-8")

    consumed = consume_authorization_atomically()
    return {
        "run_identity": run_identity,
        "result_json_sha256": sha256_file(json_path),
        "result_md_sha256": sha256_file(md_path),
        "CANONICAL_EXECUTIONS_CONSUMED": consumed["CANONICAL_EXECUTIONS_CONSUMED"],
    }


def _assemble_result_payload(
    evaluation: Mapping[str, Any], run_identity: str
) -> dict[str, Any]:
    """Bind authority fields from AUTHORITY, statistics from the evaluator.

    The RESULT cannot self-attest authority: every authority field here is
    taken from the frozen authority module, not from evaluator output.
    """
    from scripts.research.market05_cross_asset_arm_authority import (
        FROZEN_PREREG_JSON_SHA256,
        FROZEN_PREREG_MD_SHA256,
        RESEARCH_ID,
    )

    from scripts.research.market05_cross_asset_authority_root import (
        SCIENTIFIC_IMPLEMENTATION_HEAD,
        SCIENTIFIC_IMPLEMENTATION_TREE,
    )

    payload: dict[str, Any] = {key: None for key in RESULT_SCHEMA_KEYS}
    payload.update(
        {
            "research_id": RESEARCH_ID,
            "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
            "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
            # Commit provenance: exact git SHAs, never a hash map.
            "implementation_head": SCIENTIFIC_IMPLEMENTATION_HEAD,
            "implementation_tree": SCIENTIFIC_IMPLEMENTATION_TREE,
            # Per-file identity, kept separate from commit provenance.
            "scientific_implementation_hashes": dict(
                sorted(SCIENTIFIC_IMPLEMENTATION_HASHES.items())
            ),
            "btc_dataset_id": BTC_DATASET_ID,
            "btc_snapshot_id": BTC_SNAPSHOT_ID,
            "eth_dataset_id": ETH_DATASET_ID,
            "eth_snapshot_id": ETH_SNAPSHOT_ID,
            "run_identity": run_identity,
            "protected_oos_touched": False,
            "scientific_consumed": True,
        }
    )
    for key in (
        "row_counts",
        "exclusion_counts",
        "fold_counts",
        "coefficients",
        "bootstrap",
        "bootstrap_cis",
        "maes",
        "year_metrics",
        "gates",
        "classification",
    ):
        if key in evaluation:
            payload[key] = evaluation[key]
    if payload.get("classification") is None:
        payload["classification"] = CLASS_INCOMPLETE
    return payload
