"""OI-only reader for the frozen B2-06 snapshot.

Funding is not opened. A path whose name is funding.jsonl is refused.
The series field is sum_open_interest. available_at = period_start + 5 minutes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import constants as K

REPO = Path(__file__).resolve().parents[3]
OI_ROOT = REPO / "artifacts" / "research_data" / K.OI_DATASET_ID
GIT_SNAPSHOT = (
    REPO / "docs" / "research_data" / K.OI_DATASET_ID / "SNAPSHOT_5a9d036b.json"
)
FORBIDDEN_NAME = "funding.jsonl"


@dataclass(frozen=True)
class OiSeries:
    period_start_ms: np.ndarray
    available_at_ms: np.ndarray
    sum_open_interest: np.ndarray
    sha256: str
    n_rows: int
    git_snapshot_id: str
    runtime_snapshot_id: str
    funding_jsonl_opened: bool = False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_oi_identity() -> dict:
    doc = json.loads(GIT_SNAPSHOT.read_text(encoding="utf-8"))
    if doc.get("snapshot_id") != K.OI_SNAPSHOT_ID:
        raise RuntimeError("git snapshot id drifted")
    payload = doc["identity_payload"]
    if payload.get("research_authorized") is not False:
        raise RuntimeError("git snapshot authorizes research")
    found = None
    for item in payload["normalized_object_identities"]:
        if item.get("path") == "canonical/oi.jsonl":
            found = item
        if item.get("path") == f"canonical/{FORBIDDEN_NAME}":
            continue
    if found is None:
        raise RuntimeError("git snapshot has no oi.jsonl identity")
    if found["sha256"] != K.OI_JSONL_SHA256 or int(found["row_count"]) != K.OI_JSONL_ROWS:
        raise RuntimeError("git oi identity does not match the frozen constants")
    return {
        "git_snapshot_id": doc["snapshot_id"],
        "oi_sha256": found["sha256"],
        "oi_rows": int(found["row_count"]),
        "research_authorized": False,
    }


def load_bound_oi(root: Path | None = None) -> tuple[OiSeries, dict]:
    """Read sum_open_interest only. Raises if the file is not the Git-tracked object."""
    root = OI_ROOT if root is None else Path(root)
    oi_path = root / "canonical" / "oi.jsonl"
    if oi_path.name == FORBIDDEN_NAME or "funding" in oi_path.name:
        raise RuntimeError("refusing to open a funding file")
    if not oi_path.is_file():
        raise RuntimeError("OI_JSONL_MISSING")
    manifest_path = root / "reports" / "snapshot_manifest.json"
    runtime_id = None
    if manifest_path.is_file():
        runtime_id = json.loads(manifest_path.read_text(encoding="utf-8")).get("snapshot_id")
    git_id = _git_oi_identity()
    digest = _sha256(oi_path)
    if digest != K.OI_JSONL_SHA256:
        raise RuntimeError("OI_JSONL_SHA256_MISMATCH")
    starts: list[int] = []
    avails: list[int] = []
    values: list[float] = []
    with oi_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if FORBIDDEN_NAME in row or "funding_rate" in row or "sum_open_interest_value" in row:
                raise RuntimeError("OI row carries a forbidden field")
            start = int(row["period_start_ms"])
            avail = int(row["available_at_ms"])
            end = int(row["period_end_ms"])
            if avail != start + K.OI_PERIOD_MS or end != start + K.OI_PERIOD_MS:
                raise RuntimeError("OI available_at is not create_time + 5m")
            if start >= K.SURFACE_END_MS:
                raise RuntimeError("OI period starts at or after 2025-01-01")
            if str(row.get("oi_native_granularity")) != "5m":
                raise RuntimeError("OI row is not native 5m")
            starts.append(start)
            avails.append(avail)
            values.append(float(row["sum_open_interest"]))
    if len(starts) != K.OI_JSONL_ROWS:
        raise RuntimeError(f"OI_ROW_COUNT_MISMATCH:{len(starts)}")
    start_ms = np.asarray(starts, dtype=np.int64)
    avail_ms = np.asarray(avails, dtype=np.int64)
    oi_vals = np.asarray(values, dtype=np.float64)
    if np.any(np.diff(avail_ms) <= 0) or np.any(np.diff(start_ms) <= 0):
        raise RuntimeError("OI timestamps are not strictly increasing")
    if int(start_ms[0]) != K.OI_FIRST_PERIOD_START_MS or int(avail_ms[0]) != K.OI_FIRST_AVAILABLE_MS:
        raise RuntimeError("OI coverage does not start at 2020-09-01")
    series = OiSeries(
        period_start_ms=start_ms,
        available_at_ms=avail_ms,
        sum_open_interest=oi_vals,
        sha256=digest,
        n_rows=int(start_ms.shape[0]),
        git_snapshot_id=str(git_id["git_snapshot_id"]),
        runtime_snapshot_id="" if runtime_id is None else str(runtime_id),
        funding_jsonl_opened=False,
    )
    meta = {
        "dataset_id": K.OI_DATASET_ID,
        "git_snapshot_id": series.git_snapshot_id,
        "runtime_snapshot_id": series.runtime_snapshot_id,
        "oi_jsonl_sha256": digest,
        "n_rows": series.n_rows,
        "funding_jsonl_opened": False,
        "first_period_start_ms": int(start_ms[0]),
        "last_period_start_ms": int(start_ms[-1]),
        "first_available_at_ms": int(avail_ms[0]),
        "last_available_at_ms": int(avail_ms[-1]),
        "nonpositive_rows": int(np.sum(~(oi_vals > 0))),
        "research_authorized": False,
        "b2_06_evaluator_enabled": False,
    }
    return series, meta
