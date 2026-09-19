"""Outcome-blind MARKET-05 ETH execution-data binder.

Materializes 2020-01..2024-12 ETH 1m parquet from snapshot-bound official
ZIP SHA256 objects. Records structural identity only: checksums, row
counts, first/last open timestamps, schema. Does not compute Y, MAE,
coefficients, or ETH/BTC relationships. Does not open 2025/2026 ZIPs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

UTC = timezone.utc

ETH_SNAPSHOT_DOC_REL = "docs/research_data/CORE_ETH_BINANCE_V0/SNAPSHOT_4b9c113f.json"
ETH_SNAPSHOT_ID = "4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15"
ETH_DATASET_ID = "CORE_ETH_BINANCE_V0"
BINDING_REL = "docs/research_data/CORE_ETH_BINANCE_V0/MARKET_05_EXECUTION_BINDING.json"
ETH_ZIP_ROOT_REL = "artifacts/research_data/CORE_ETH_BINANCE_V0/raw"
ETH_PARQUET_ROOT_REL = "artifacts/research_data/CORE_ETH_BINANCE_V0"
MATERIALIZER_VERSION = "market05_eth_execution_parquet/1.0.0"
DEVELOPMENT_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
PROTECTED_OOS_START = "2025-01-01T00:00:00Z"
PARQUET_WRITE_KWARGS = {
    "compression": "zstd",
    "use_dictionary": False,
    "write_statistics": False,
    "store_schema": False,
}
REQUIRED_COLUMNS = ("open_time_ms", "high", "low", "close")
SCHEMA_DESCRIPTION = {
    "open_time_ms": "int64",
    "high": "decimal_string",
    "low": "decimal_string",
    "close": "decimal_string",
}


class Market05EthBindingError(RuntimeError):
    """ETH execution-data binding / materialization failure."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dec_str(value: Decimal) -> str:
    return format(value, "f")


def development_objects(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    objects = snapshot.get("objects") or []
    selected: list[dict[str, Any]] = []
    for obj in objects:
        period = str(obj.get("source_period") or "")
        if period >= "2025-01":
            continue
        if str(obj.get("archive_class")) != "monthly":
            continue
        selected.append(dict(obj))
    if len(selected) != 60:
        raise Market05EthBindingError(
            f"MARKET_05_ETH_DEVELOPMENT_OBJECT_COUNT:{len(selected)}"
        )
    return selected


def load_accepted_eth_snapshot(repo: Path | None = None) -> dict[str, Any]:
    root = repo or _repo_root()
    path = root / ETH_SNAPSHOT_DOC_REL
    if path.is_symlink() or not path.is_file():
        raise Market05EthBindingError("MARKET_05_ETH_SNAPSHOT_DOC_MISSING")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("snapshot_id") != ETH_SNAPSHOT_ID:
        raise Market05EthBindingError("MARKET_05_ETH_SNAPSHOT_ID_MISMATCH")
    if payload.get("dataset_id") != ETH_DATASET_ID:
        raise Market05EthBindingError("MARKET_05_ETH_DATASET_ID_MISMATCH")
    return payload


def _write_ohlc_parquet(rows: list[dict[str, Any]], dest: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    dest.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "open_time_ms": pa.array(
                [int(r["open_time_ms"]) for r in rows], type=pa.int64()
            ),
            "high": pa.array([r["high"] for r in rows], type=pa.string()),
            "low": pa.array([r["low"] for r in rows], type=pa.string()),
            "close": pa.array([r["close"] for r in rows], type=pa.string()),
        }
    )
    buf = pa.BufferOutputStream()
    pq.write_table(table, buf, **PARQUET_WRITE_KWARGS)
    dest.write_bytes(buf.getvalue().to_pybytes())


def materialize_one_object(
    obj: Mapping[str, Any], *, repo: Path, zip_root: Path, parquet_root: Path
) -> dict[str, Any]:
    from scripts.research.core_btc_binance_v0_probe_lib import (
        parse_kline_csv,
        read_kline_csv_member_named,
    )
    from scripts.research.core_eth_binance_v0_acceptor_lib import expected_csv_member

    zip_name = str(obj["expected_zip_filename"])
    if "2025-" in zip_name or "2026-" in zip_name or "2027-" in zip_name:
        raise Market05EthBindingError(f"MARKET_05_ETH_PROTECTED_ZIP_REFUSED:{zip_name}")
    zip_path = zip_root / zip_name
    if zip_path.is_symlink() or not zip_path.is_file():
        raise Market05EthBindingError(f"MARKET_05_ETH_ZIP_MISSING:{zip_name}")
    zip_sha = sha256_file(zip_path)
    expected_zip = str(obj["zip_sha256"])
    if zip_sha != expected_zip:
        raise Market05EthBindingError(f"MARKET_05_ETH_ZIP_SHA256_MISMATCH:{zip_name}")
    member = expected_csv_member(str(obj["archive_class"]), str(obj["source_period"]))
    text, _names, status = read_kline_csv_member_named(zip_path, member)
    if status != "OK" or text is None:
        raise Market05EthBindingError(
            f"MARKET_05_ETH_CSV_MEMBER_FAIL:{zip_name}:{status}"
        )
    parsed, meta = parse_kline_csv(text)
    if int(meta.get("malformed_row_count") or 0) != 0:
        raise Market05EthBindingError(f"MARKET_05_ETH_MALFORMED:{zip_name}")
    if len(parsed) != int(obj["observed_rows"]):
        raise Market05EthBindingError(f"MARKET_05_ETH_ROW_COUNT:{zip_name}")
    if int(parsed[0].open_time_ms) != int(obj["first_open_time_ms"]):
        raise Market05EthBindingError(f"MARKET_05_ETH_FIRST_OPEN:{zip_name}")
    if int(parsed[-1].open_time_ms) != int(obj["last_open_time_ms"]):
        raise Market05EthBindingError(f"MARKET_05_ETH_LAST_OPEN:{zip_name}")
    rel = f"canonical/1m/monthly/{obj['source_period']}.parquet"
    dest = parquet_root / rel
    rows = [
        {
            "open_time_ms": int(row.open_time_ms),
            "high": _dec_str(row.high),
            "low": _dec_str(row.low),
            "close": _dec_str(row.close),
        }
        for row in parsed
    ]
    _write_ohlc_parquet(rows, dest)
    if dest.is_symlink():
        raise Market05EthBindingError(f"MARKET_05_ETH_PARQUET_SYMLINK:{rel}")
    return {
        "source_official_zip_filename": zip_name,
        "source_zip_sha256": expected_zip,
        "source_period": obj["source_period"],
        "archive_class": obj["archive_class"],
        "deterministic_materialization_procedure": MATERIALIZER_VERSION,
        "canonical_parquet_relative_path": rel,
        "canonical_parquet_sha256": sha256_file(dest),
        "row_count": len(rows),
        "first_open_time_ms": int(parsed[0].open_time_ms),
        "last_open_time_ms": int(parsed[-1].open_time_ms),
        "schema": dict(SCHEMA_DESCRIPTION),
    }


def build_execution_binding(repo: Path | None = None) -> dict[str, Any]:
    root = repo or _repo_root()
    snapshot = load_accepted_eth_snapshot(root)
    objects = development_objects(snapshot)
    zip_root = root / ETH_ZIP_ROOT_REL
    parquet_root = root / ETH_PARQUET_ROOT_REL
    records = [
        materialize_one_object(
            obj, repo=root, zip_root=zip_root, parquet_root=parquet_root
        )
        for obj in objects
    ]
    payload = {
        "schema": "market_05_eth_execution_binding",
        "schema_version": "1.0.0",
        "dataset_id": ETH_DATASET_ID,
        "eth_snapshot_id": ETH_SNAPSHOT_ID,
        "development_start_inclusive": "2020-01-01T00:00:00Z",
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "protected_oos_start": PROTECTED_OOS_START,
        "protected_oos_objects_materialized": False,
        "price_values_scientifically_evaluated": False,
        "materializer_version": MATERIALIZER_VERSION,
        "parquet_root_relative": ETH_PARQUET_ROOT_REL,
        "zip_root_relative": ETH_ZIP_ROOT_REL,
        "required_columns": list(REQUIRED_COLUMNS),
        "object_count": len(records),
        "objects": records,
        "scientific_outcomes_inspected": False,
        "protected_oos_touched": False,
    }
    ident = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    payload["eth_execution_data_id"] = ident
    return payload


def write_execution_binding(repo: Path | None = None) -> dict[str, Any]:
    root = repo or _repo_root()
    payload = build_execution_binding(root)
    dest = root / BINDING_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(canonical_json_bytes(payload))
    return payload


def load_execution_binding(repo: Path | None = None) -> dict[str, Any]:
    root = repo or _repo_root()
    path = root / BINDING_REL
    if path.is_symlink() or not path.is_file():
        raise Market05EthBindingError("MARKET_05_ETH_EXECUTION_BINDING_MISSING")
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = payload.get("eth_execution_data_id")
    identity_payload = {k: v for k, v in payload.items() if k != "eth_execution_data_id"}
    recomputed = hashlib.sha256(canonical_json_bytes(identity_payload)).hexdigest()
    if stored != recomputed:
        raise Market05EthBindingError("MARKET_05_ETH_EXECUTION_DATA_ID_MISMATCH")
    if payload.get("eth_snapshot_id") != ETH_SNAPSHOT_ID:
        raise Market05EthBindingError("MARKET_05_ETH_BINDING_SNAPSHOT_MISMATCH")
    return payload


if __name__ == "__main__":
    result = write_execution_binding()
    print(result["eth_execution_data_id"])
    print(result["object_count"])
