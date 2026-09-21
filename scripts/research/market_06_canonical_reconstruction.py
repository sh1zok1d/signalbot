"""MARKET-06 canonical dataset reconstruction from Git-retained bytes.

Repairs red-team F-06: previously no reconstruction existed at all, so
per-object duplicate checks could not catch a timestamp duplicated across
two different monthly objects or OKX pages, and no global completeness
invariant was ever enforced.

Network-free by construction: every byte is read from an immutable Git
object. Nothing is downloaded, re-downloaded, interpolated, forward-filled,
or de-duplicated. A cross-object duplicate is INCOMPLETE_EXECUTION even
when the duplicated values happen to be identical.

Requires an authenticated execution permit. Without one, canonical
reconstruction refuses (the retained bytes are not parseable).

Reports timestamp-only structure. It never returns, prints, or logs OHLC
values.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scripts.research import market_06_git_authority as gitauth
from scripts.research import market_06_execution_lifecycle as lifecycle
from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06IncompleteExecution,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import (
    BAR_MS,
    WINDOW_END_EXCLUSIVE_MS,
    WINDOW_START_MS,
    PerpBar,
    parse_binance_zip_bytes,
    parse_okx_history_body,
)

DATASET_DIR_REL = "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
DURABLE_MANIFEST_REL = f"{DATASET_DIR_REL}/DURABLE_RETENTION_MANIFEST.json"

BINANCE_OBJECT_COUNT = 36
OKX_OBJECT_COUNT = 1053
EXPECTED_5M_TIMESTAMPS = 315648

EXPECTED_FIRST_MS = WINDOW_START_MS
EXPECTED_LAST_MS = WINDOW_END_EXCLUSIVE_MS - BAR_MS


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(commit: str) -> dict[str, Any]:
    raw = gitauth.cat_blob(commit, DURABLE_MANIFEST_REL)
    manifest = json.loads(raw.decode("utf-8"))
    if manifest.get("dataset_id") != lifecycle.DATASET_ID:
        raise Market06IncompleteExecution("MANIFEST_DATASET_ID")
    if manifest.get("snapshot_id") != lifecycle.SNAPSHOT_ID:
        raise Market06IncompleteExecution("MANIFEST_SNAPSHOT_ID")
    if manifest.get("durable_evidence_root_sha256") != lifecycle.DURABLE_EVIDENCE_ROOT_SHA256:
        raise Market06IncompleteExecution("MANIFEST_DURABLE_ROOT")
    binance = manifest.get("binance_objects") or []
    okx = manifest.get("okx_objects") or []
    if len(binance) != BINANCE_OBJECT_COUNT:
        raise Market06IncompleteExecution("MANIFEST_BINANCE_COUNT")
    if len(okx) != OKX_OBJECT_COUNT:
        raise Market06IncompleteExecution("MANIFEST_OKX_COUNT")
    return manifest


def _require_unique_inventory(rows: list[Mapping[str, Any]], *, leg: str) -> None:
    """Every expected raw object appears exactly once; none unexpected.

    Inventory order must not matter, so identity is a set of logical ids.
    """

    ids = [str(row["logical_id"]) for row in rows]
    paths = [str(row["durable_path"]) for row in rows]
    digests = [str(row["sha256"]) for row in rows]
    if len(set(ids)) != len(ids):
        raise Market06IncompleteExecution(f"INVENTORY_DUPLICATE_LOGICAL_ID:{leg}")
    if len(set(paths)) != len(paths):
        raise Market06IncompleteExecution(f"INVENTORY_DUPLICATE_PATH:{leg}")
    if len(set(digests)) != len(digests):
        raise Market06IncompleteExecution(f"INVENTORY_DUPLICATE_SHA256:{leg}")


def _read_retained_object(commit: str, row: Mapping[str, Any], *, leg: str) -> bytes:
    rel = f"{DATASET_DIR_REL}/{row['durable_path']}"
    blob = gitauth.cat_blob(commit, rel)
    digest = _sha256(blob)
    if digest != str(row["sha256"]):
        raise Market06IncompleteExecution(f"RETAINED_OBJECT_SHA256:{leg}:{row['logical_id']}")
    if len(blob) != int(row["byte_length"]):
        raise Market06IncompleteExecution(
            f"RETAINED_OBJECT_BYTE_LENGTH:{leg}:{row['logical_id']}"
        )
    return blob


def _in_window(ts: int) -> bool:
    return WINDOW_START_MS <= ts < WINDOW_END_EXCLUSIVE_MS


def _merge_unique(
    target: dict[int, Any],
    origin: dict[int, str],
    items: list[tuple[int, Any]],
    *,
    leg: str,
    logical_id: str,
) -> int:
    """Insert in-window observations, rejecting ANY cross-object duplicate."""

    trimmed = 0
    for ts, value in items:
        if not _in_window(ts):
            trimmed += 1
            continue
        if ts in target:
            raise Market06IncompleteExecution(
                f"GLOBAL_DUPLICATE_TIMESTAMP:{leg}:{ts}:{origin[ts]}:{logical_id}"
            )
        target[ts] = value
        origin[ts] = logical_id
    return trimmed


def _assert_complete_grid(timestamps: set[int], *, leg: str) -> None:
    if len(timestamps) != EXPECTED_5M_TIMESTAMPS:
        raise Market06IncompleteExecution(
            f"TIMESTAMP_COUNT:{leg}:{len(timestamps)}:{EXPECTED_5M_TIMESTAMPS}"
        )
    low = min(timestamps)
    high = max(timestamps)
    if low != EXPECTED_FIRST_MS:
        raise Market06IncompleteExecution(f"FIRST_TIMESTAMP:{leg}:{low}")
    if high != EXPECTED_LAST_MS:
        raise Market06IncompleteExecution(f"LAST_TIMESTAMP:{leg}:{high}")
    for ts in timestamps:
        if ts % BAR_MS != 0:
            raise Market06IncompleteExecution(f"NOT_5M_ALIGNED:{leg}:{ts}")
    # Count + exact endpoints + alignment + uniqueness already imply a
    # complete contiguous grid, but prove it directly rather than by argument.
    expected_span = (EXPECTED_LAST_MS - EXPECTED_FIRST_MS) // BAR_MS + 1
    if expected_span != EXPECTED_5M_TIMESTAMPS:
        raise Market06IncompleteExecution(f"GRID_SPAN:{leg}:{expected_span}")
    missing = expected_span - len(timestamps)
    if missing != 0:
        raise Market06IncompleteExecution(f"MISSING_TIMESTAMPS:{leg}:{missing}")


def reconstruct_canonical_dataset(
    permit: Any,
    *,
    source_commit: str | None = None,
) -> tuple[dict[int, PerpBar], dict[int, float], dict[str, Any]]:
    """Reconstruct the canonical perp/spot maps under an authenticated permit.

    Returns ``(perp_by_open_time, spot_close_by_open_time, audit)`` where
    ``audit`` is timestamp-only structural provenance with no OHLC values.
    """

    authenticated = lifecycle.require_permit(permit)
    commit = source_commit or lifecycle.PREREG_FREEZE_HEAD
    resolved = gitauth.require_commit(commit, label="retained_source_commit")

    manifest = load_manifest(resolved)
    binance_rows = list(manifest["binance_objects"])
    okx_rows = list(manifest["okx_objects"])
    _require_unique_inventory(binance_rows, leg="binance")
    _require_unique_inventory(okx_rows, leg="okx")

    perp: dict[int, PerpBar] = {}
    perp_origin: dict[int, str] = {}
    perp_trimmed = 0
    for row in binance_rows:
        blob = _read_retained_object(resolved, row, leg="binance")
        bars = parse_binance_zip_bytes(
            blob,
            zip_name=str(row["original_filename"]),
            permit=authenticated,
        )
        perp_trimmed += _merge_unique(
            perp,
            perp_origin,
            [(bar.open_time_ms, bar) for bar in bars],
            leg="binance",
            logical_id=str(row["logical_id"]),
        )

    spot: dict[int, float] = {}
    spot_origin: dict[int, str] = {}
    spot_trimmed = 0
    for row in okx_rows:
        blob = _read_retained_object(resolved, row, leg="okx")
        closes = parse_okx_history_body(
            blob,
            source=str(row["original_filename"]),
            permit=authenticated,
        )
        spot_trimmed += _merge_unique(
            spot,
            spot_origin,
            [(item.open_time_ms, item.close) for item in closes],
            leg="okx",
            logical_id=str(row["logical_id"]),
        )

    _assert_complete_grid(set(perp), leg="binance")
    _assert_complete_grid(set(spot), leg="okx")
    if set(perp) != set(spot):
        only_perp = len(set(perp) - set(spot))
        only_spot = len(set(spot) - set(perp))
        raise Market06IncompleteExecution(
            f"LEG_TIMESTAMP_SETS_DIFFER:{only_perp}:{only_spot}"
        )

    audit = {
        "dataset_id": authenticated.dataset_id,
        "snapshot_id": authenticated.snapshot_id,
        "durable_evidence_root_sha256": authenticated.durable_evidence_root_sha256,
        "run_identity": authenticated.run_identity,
        "source_commit": resolved,
        "binance_objects": len(binance_rows),
        "okx_objects": len(okx_rows),
        "binance_timestamps": len(perp),
        "okx_timestamps": len(spot),
        "expected_timestamps": EXPECTED_5M_TIMESTAMPS,
        "first_timestamp_ms": EXPECTED_FIRST_MS,
        "last_timestamp_ms": EXPECTED_LAST_MS,
        "binance_out_of_window_trimmed": perp_trimmed,
        "okx_out_of_window_trimmed": spot_trimmed,
        "interpolation": False,
        "forward_fill": False,
        "deduplication": False,
        "leg_timestamp_sets_equal": True,
        "ohlc_values_reported": False,
        "scientific_outcomes_inspected": False,
    }
    return perp, spot, audit
