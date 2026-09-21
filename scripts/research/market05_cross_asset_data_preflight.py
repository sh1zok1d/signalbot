"""Outcome-blind MARKET-05 structural data preflight.

Runs BEFORE the atomic execution claim. Verifies required files, exact
checksums, exact object sets, parquet schema columns, and timestamp
metadata. Does not construct Y, MAE, coefficients, or ETH/BTC relationships.
Does not parse protected 2025/2026 objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

BTC_DATASET_ROOT_REL = "artifacts/research_data/CORE_BTC_BINANCE_V0"
ETH_DATASET_ROOT_REL = "artifacts/research_data/CORE_ETH_BINANCE_V0"
BTC_SNAPSHOT_DOC_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
REQUIRED_OHLC_COLUMNS = ("open_time_ms", "high", "low", "close")
PROTECTED_FILENAME_PREFIXES = ("2025-", "2026-", "2027-")


class Market05PreflightError(RuntimeError):
    """Structural preflight failed; the execution claim must not be created."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _path(rel: str) -> Path:
    return _repo_root() / rel


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def btc_development_parquet_rels(snapshot: Mapping[str, Any]) -> list[str]:
    identity = snapshot.get("identity_payload") or snapshot
    checksums = identity.get("output_checksums") or {}
    selected: list[str] = []
    for rel in checksums:
        if not rel.startswith("canonical/1m/monthly/") or not rel.endswith(".parquet"):
            continue
        name = Path(rel).name
        if name.startswith(PROTECTED_FILENAME_PREFIXES):
            continue
        period = name[: len("YYYY-MM")]
        if period < "2020-01" or period > "2024-12":
            continue
        selected.append(rel)
    selected.sort()
    if len(selected) != 60:
        raise Market05PreflightError(
            f"MARKET_05_BTC_DEVELOPMENT_OBJECT_COUNT:{len(selected)}"
        )
    return selected


def _load_json(rel: str) -> dict[str, Any]:
    path = _path(rel)
    if path.is_symlink():
        raise Market05PreflightError(f"MARKET_05_PREFLIGHT_SYMLINK:{rel}")
    if not path.is_file():
        raise Market05PreflightError(f"MARKET_05_PREFLIGHT_MISSING:{rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def _require_regular_file(path: Path, label: str) -> None:
    if path.is_symlink():
        raise Market05PreflightError(f"MARKET_05_DATASET_SYMLINK_REFUSED:{label}")
    if not path.is_file():
        raise Market05PreflightError(f"MARKET_05_INCOMPLETE_EXECUTION:missing:{label}")


def _parquet_schema_names(path: Path) -> set[str]:
    import pyarrow.parquet as pq

    schema = pq.read_schema(path)
    return set(schema.names)


def _parquet_timestamp_bounds(path: Path) -> tuple[int, int, int]:
    import pyarrow.parquet as pq

    table = pq.read_table(path, columns=["open_time_ms"])
    opens = [int(v) for v in table.column("open_time_ms").to_pylist()]
    if not opens:
        raise Market05PreflightError(f"MARKET_05_PREFLIGHT_EMPTY_PARQUET:{path.name}")
    return len(opens), min(opens), max(opens)


def verify_btc_development_set() -> dict[str, Any]:
    snapshot = _load_json(BTC_SNAPSHOT_DOC_REL)
    identity = snapshot.get("identity_payload") or snapshot
    checksums = identity.get("output_checksums") or {}
    rels = btc_development_parquet_rels(snapshot)
    root = _path(BTC_DATASET_ROOT_REL)
    if not root.is_dir():
        raise Market05PreflightError("MARKET_05_CORE_DATASET_MISSING:CORE_BTC_BINANCE_V0")
    verified: list[str] = []
    for rel in rels:
        path = root / rel
        _require_regular_file(path, rel)
        expected = checksums.get(rel)
        if expected is None:
            raise Market05PreflightError(f"MARKET_05_CORE_CHECKSUM_UNBOUND:BTC:{rel}")
        actual = sha256_file(path)
        if actual != expected:
            raise Market05PreflightError(f"MARKET_05_CORE_CHECKSUM_MISMATCH:BTC:{rel}")
        names = _parquet_schema_names(path)
        missing = [c for c in REQUIRED_OHLC_COLUMNS if c not in names]
        if missing:
            raise Market05PreflightError(
                f"MARKET_05_BTC_SCHEMA_MISSING:{rel}:{missing}"
            )
        n, first_ms, last_ms = _parquet_timestamp_bounds(path)
        if n <= 0 or last_ms < first_ms:
            raise Market05PreflightError(f"MARKET_05_BTC_TIMESTAMP_METADATA:{rel}")
        # Structural only: refuse if this development object contains OOS opens.
        from datetime import datetime, timezone

        oos = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        if last_ms >= oos:
            raise Market05PreflightError(f"MARKET_05_BTC_OBJECT_SPANS_PROTECTED_OOS:{rel}")
        verified.append(rel)
    return {"btc_objects": verified, "btc_object_count": len(verified)}


def verify_eth_execution_binding() -> dict[str, Any]:
    from scripts.research.market05_eth_execution_binding import (
        ETH_PARQUET_ROOT_REL,
        REQUIRED_COLUMNS,
        load_execution_binding,
    )

    binding = load_execution_binding(_repo_root())
    root = _path(ETH_PARQUET_ROOT_REL)
    verified: list[str] = []
    for obj in binding["objects"]:
        rel = str(obj["canonical_parquet_relative_path"])
        name = Path(rel).name
        if name.startswith(PROTECTED_FILENAME_PREFIXES):
            raise Market05PreflightError(f"MARKET_05_ETH_PROTECTED_OBJECT_IN_BINDING:{rel}")
        path = root / rel
        _require_regular_file(path, rel)
        actual = sha256_file(path)
        if actual != obj["canonical_parquet_sha256"]:
            raise Market05PreflightError(f"MARKET_05_CORE_CHECKSUM_MISMATCH:ETH:{rel}")
        names = _parquet_schema_names(path)
        missing = [c for c in REQUIRED_COLUMNS if c not in names]
        if missing:
            raise Market05PreflightError(f"MARKET_05_ETH_SCHEMA_MISSING:{rel}:{missing}")
        n, first_ms, last_ms = _parquet_timestamp_bounds(path)
        if n != int(obj["row_count"]):
            raise Market05PreflightError(f"MARKET_05_ETH_ROW_COUNT:{rel}")
        if first_ms != int(obj["first_open_time_ms"]) or last_ms != int(
            obj["last_open_time_ms"]
        ):
            raise Market05PreflightError(f"MARKET_05_ETH_TIMESTAMP_METADATA:{rel}")
        verified.append(rel)
    if len(verified) != 60:
        raise Market05PreflightError(
            f"MARKET_05_ETH_DEVELOPMENT_OBJECT_COUNT:{len(verified)}"
        )
    return {
        "eth_objects": verified,
        "eth_object_count": len(verified),
        "eth_execution_data_id": binding["eth_execution_data_id"],
    }


def run_structural_preflight() -> dict[str, Any]:
    btc = verify_btc_development_set()
    eth = verify_eth_execution_binding()
    return {**btc, **eth}
