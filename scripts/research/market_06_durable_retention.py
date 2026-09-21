"""Outcome-blind durable retention for MARKET_06_OKX_BINANCE_FEASIBILITY_V0.

Copies already-materialized raw bytes into Git-tracked durable storage
after fail-closed verification against the frozen feasibility manifests.
Does not redownload. Does not parse OHLC for science. Does not mint a
new snapshot identity.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO / "docs" / "research_data" / "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
RUNTIME_ROOT = REPO / "artifacts" / "research_data" / "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
DURABLE_RAW = DOCS_ROOT / "durable_raw"
MANIFEST_REL = "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/DURABLE_RETENTION_MANIFEST.json"
MANIFEST_PATH = REPO / MANIFEST_REL

DATASET_ID = "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
SNAPSHOT_ID = "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"
SOURCE_FEASIBILITY_HEAD = "ef439110684e5bef5d6b6f31b664c21a114111b2"
BINANCE_OBJECT_COUNT = 36
OKX_PAGE_COUNT = 1053
IDENTITY_FILES = (
    "binance_object_ledger.json",
    "okx_page_manifest.json",
    "timestamp_census.json",
    "snapshot.json",
)
CHECKSUM_LINE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(\S+)\s*$")


class DurableRetentionError(RuntimeError):
    """Fail-closed durable retention / recovery error."""


class DurableRetentionMismatch(DurableRetentionError):
    verdict = "MARKET_06_DURABLE_RETENTION_SOURCE_BYTES_MISMATCH"


class DurableRetentionMissing(DurableRetentionError):
    verdict = "MARKET_06_DURABLE_RETENTION_LOCAL_BYTES_MISSING"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def write_canonical_json(path: Path, payload: Mapping[str, Any]) -> str:
    data = canonical_json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)


def copy_exact(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def recompute_snapshot_id(identity_dir: Path) -> str:
    hashes = {
        name: sha256_bytes((identity_dir / name).read_bytes()) for name in IDENTITY_FILES
    }
    preimage = (json.dumps(hashes, sort_keys=True) + "\n").encode("utf-8")
    return sha256_bytes(preimage)


def require_snapshot_id(identity_dir: Path) -> str:
    actual = recompute_snapshot_id(identity_dir)
    if actual != SNAPSHOT_ID:
        raise DurableRetentionMismatch(
            f"SNAPSHOT_ID_MISMATCH:expected={SNAPSHOT_ID}:actual={actual}"
        )
    recorded = load_json(identity_dir / "HASHES.json").get("snapshot_id")
    if recorded != SNAPSHOT_ID:
        raise DurableRetentionMismatch(
            f"HASHES_SNAPSHOT_ID_MISMATCH:expected={SNAPSHOT_ID}:actual={recorded}"
        )
    return actual


def _parse_checksum_sidecar(text: str, expected_name: str) -> str:
    line = text.strip().splitlines()[0].strip()
    match = CHECKSUM_LINE.match(line)
    if not match:
        raise DurableRetentionMismatch(f"CHECKSUM_SIDECAR_UNPARSEABLE:{expected_name}")
    digest, name = match.group(1).lower(), match.group(2)
    if name != expected_name:
        raise DurableRetentionMismatch(
            f"CHECKSUM_FILENAME_MISMATCH:{name}:{expected_name}"
        )
    return digest


def inspect_runtime_raw(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    identity_dir: Path = DOCS_ROOT,
) -> dict[str, Any]:
    """Verify existing local raw bytes against frozen manifests. No network."""
    missing: list[str] = []
    mismatches: list[str] = []
    require_snapshot_id(identity_dir)
    ledger = load_json(identity_dir / "binance_object_ledger.json")
    pages = load_json(identity_dir / "okx_page_manifest.json")
    if len(ledger) != BINANCE_OBJECT_COUNT:
        raise DurableRetentionMismatch(
            f"BINANCE_LEDGER_COUNT:{len(ledger)}:{BINANCE_OBJECT_COUNT}"
        )
    if len(pages) != OKX_PAGE_COUNT:
        raise DurableRetentionMismatch(f"OKX_MANIFEST_COUNT:{len(pages)}:{OKX_PAGE_COUNT}")

    binance_objects: list[dict[str, Any]] = []
    for item in ledger:
        period = item["period"]
        zip_name = f"BTCUSDT-5m-{period}.zip"
        zip_path = runtime_root / "raw" / "binance" / zip_name
        cs_path = runtime_root / "raw" / "binance" / f"{zip_name}.CHECKSUM"
        if not zip_path.is_file():
            missing.append(str(zip_path))
            continue
        data = zip_path.read_bytes()
        digest = sha256_bytes(data)
        if len(data) != int(item["byte_size"]):
            mismatches.append(f"BINANCE_SIZE:{zip_name}:{item['byte_size']}:{len(data)}")
        if digest != item["local_sha256"] or digest != item["expected_sha256"]:
            mismatches.append(f"BINANCE_SHA256:{zip_name}")
        if item.get("checksum_verification") != "VERIFIED":
            mismatches.append(f"BINANCE_CHECKSUM_VERDICT:{zip_name}:{item.get('checksum_verification')}")
        sidecar_sha = None
        sidecar_len = None
        if not cs_path.is_file():
            missing.append(str(cs_path))
        else:
            cs_bytes = cs_path.read_bytes()
            sidecar_sha = sha256_bytes(cs_bytes)
            sidecar_len = len(cs_bytes)
            named = _parse_checksum_sidecar(cs_bytes.decode("utf-8"), zip_name)
            if named != item["expected_sha256"]:
                mismatches.append(f"BINANCE_CHECKSUM_SIDECAR:{zip_name}")
        binance_objects.append(
            {
                "logical_id": f"BINANCE_BTCUSDT_5M_{period}",
                "kind": "binance_zip",
                "period": period,
                "original_filename": zip_name,
                "runtime_path": str(zip_path.relative_to(runtime_root)),
                "durable_path": f"durable_raw/binance/{zip_name}",
                "byte_length": len(data),
                "sha256": digest,
                "checksum_verification": item["checksum_verification"],
                "checksum_sidecar_filename": f"{zip_name}.CHECKSUM",
                "checksum_sidecar_durable_path": f"durable_raw/binance/{zip_name}.CHECKSUM",
                "checksum_sidecar_byte_length": sidecar_len,
                "checksum_sidecar_sha256": sidecar_sha,
            }
        )

    okx_objects: list[dict[str, Any]] = []
    for item in pages:
        rel = item["path"]
        page_path = runtime_root / rel
        if not page_path.is_file():
            missing.append(str(page_path))
            continue
        data = page_path.read_bytes()
        digest = sha256_bytes(data)
        if len(data) != int(item["byte_size"]):
            mismatches.append(f"OKX_SIZE:{rel}:{item['byte_size']}:{len(data)}")
        if digest != item["payload_sha256"]:
            mismatches.append(f"OKX_SHA256:{rel}")
        req = dict(item["request"])
        if req.get("instId") != "BTC-USDT" or req.get("bar") != "5m":
            mismatches.append(f"OKX_REQUEST:{rel}")
        page_name = Path(rel).name
        okx_objects.append(
            {
                "logical_id": f"OKX_PAGE_{int(item['page_index']):06d}",
                "kind": "okx_http_body",
                "page_id": int(item["page_index"]),
                "original_filename": page_name,
                "request": req,
                "runtime_path": rel,
                "durable_path": f"durable_raw/okx/{page_name}",
                "byte_length": len(data),
                "sha256": digest,
            }
        )

    if missing:
        raise DurableRetentionMissing("MISSING:" + ",".join(missing[:20]))
    if mismatches:
        raise DurableRetentionMismatch("MISMATCH:" + ",".join(mismatches[:20]))
    if len(binance_objects) != BINANCE_OBJECT_COUNT:
        raise DurableRetentionMismatch(f"BINANCE_RETAIN_COUNT:{len(binance_objects)}")
    if len(okx_objects) != OKX_PAGE_COUNT:
        raise DurableRetentionMismatch(f"OKX_RETAIN_COUNT:{len(okx_objects)}")
    return {
        "binance_objects": binance_objects,
        "okx_objects": okx_objects,
        "snapshot_id": SNAPSHOT_ID,
    }


def ordered_inventory(inspected: Mapping[str, Any]) -> list[dict[str, Any]]:
    binance = sorted(inspected["binance_objects"], key=lambda row: row["logical_id"])
    okx = sorted(inspected["okx_objects"], key=lambda row: int(row["page_id"]))
    return list(binance) + list(okx)


def durable_root_payload(inspected: Mapping[str, Any]) -> dict[str, Any]:
    objects = []
    for row in ordered_inventory(inspected):
        entry = {
            "byte_length": int(row["byte_length"]),
            "kind": row["kind"],
            "logical_id": row["logical_id"],
            "sha256": row["sha256"],
        }
        objects.append(entry)
    return {
        "schema": "signalbot_market_06_okx_binance_feasibility_v0_durable_evidence_root",
        "schema_version": "1.0.0",
        "dataset_id": DATASET_ID,
        "snapshot_id": SNAPSHOT_ID,
        "source_feasibility_head": SOURCE_FEASIBILITY_HEAD,
        "binance_object_count": BINANCE_OBJECT_COUNT,
        "okx_page_count": OKX_PAGE_COUNT,
        "objects": objects,
    }


def durable_evidence_root_sha256(inspected: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(durable_root_payload(inspected)))


def retain_exact_bytes(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    identity_dir: Path = DOCS_ROOT,
    durable_raw: Path = DURABLE_RAW,
) -> dict[str, Any]:
    inspected = inspect_runtime_raw(runtime_root=runtime_root, identity_dir=identity_dir)
    for row in inspected["binance_objects"]:
        src = runtime_root / row["runtime_path"]
        dest = identity_dir / row["durable_path"]
        copy_exact(src, dest)
        if sha256_bytes(dest.read_bytes()) != row["sha256"]:
            raise DurableRetentionMismatch(f"COPY_SHA256:{row['logical_id']}")
        cs_src = runtime_root / "raw" / "binance" / row["checksum_sidecar_filename"]
        cs_dest = identity_dir / row["checksum_sidecar_durable_path"]
        copy_exact(cs_src, cs_dest)
        if sha256_bytes(cs_dest.read_bytes()) != row["checksum_sidecar_sha256"]:
            raise DurableRetentionMismatch(f"COPY_CHECKSUM_SHA256:{row['logical_id']}")
    for row in inspected["okx_objects"]:
        src = runtime_root / row["runtime_path"]
        dest = identity_dir / row["durable_path"]
        copy_exact(src, dest)
        if sha256_bytes(dest.read_bytes()) != row["sha256"]:
            raise DurableRetentionMismatch(f"COPY_SHA256:{row['logical_id']}")
    root_sha = durable_evidence_root_sha256(inspected)
    manifest = {
        "schema": "signalbot_market_06_okx_binance_feasibility_v0_durable_retention",
        "schema_version": "1.0.0",
        "dataset_id": DATASET_ID,
        "snapshot_id": SNAPSHOT_ID,
        "source_feasibility_head": SOURCE_FEASIBILITY_HEAD,
        "scientific_outcomes_inspected": False,
        "dislocation_computed": False,
        "future_returns_computed": False,
        "2025_opened": False,
        "2026_opened": False,
        "market_06_prereg_created": False,
        "market_06_arm_created": False,
        "market_06_result_created": False,
        "binance_object_count": BINANCE_OBJECT_COUNT,
        "okx_page_count": OKX_PAGE_COUNT,
        "raw_bytes_git_retained": True,
        "retention_method": "DIRECT_EXACT_BYTE_FILES",
        "durable_evidence_root_sha256": root_sha,
        "identity_files_unchanged": True,
        "new_snapshot_minted": False,
        "binance_objects": sorted(
            inspected["binance_objects"], key=lambda row: row["logical_id"]
        ),
        "okx_objects": sorted(
            inspected["okx_objects"], key=lambda row: int(row["page_id"])
        ),
    }
    write_canonical_json(identity_dir / "DURABLE_RETENTION_MANIFEST.json", manifest)
    verify_durable_offline(identity_dir=identity_dir)
    return manifest


def verify_durable_offline(*, identity_dir: Path = DOCS_ROOT) -> dict[str, Any]:
    """Recover every retained object from tracked durable bytes. No network."""
    require_snapshot_id(identity_dir)
    ledger = load_json(identity_dir / "binance_object_ledger.json")
    pages = load_json(identity_dir / "okx_page_manifest.json")
    manifest = load_json(identity_dir / "DURABLE_RETENTION_MANIFEST.json")
    if manifest["snapshot_id"] != SNAPSHOT_ID:
        raise DurableRetentionMismatch("MANIFEST_SNAPSHOT_ID")
    if manifest["dataset_id"] != DATASET_ID:
        raise DurableRetentionMismatch("MANIFEST_DATASET_ID")
    if len(manifest["binance_objects"]) != BINANCE_OBJECT_COUNT:
        raise DurableRetentionMismatch("MANIFEST_BINANCE_COUNT")
    if len(manifest["okx_objects"]) != OKX_PAGE_COUNT:
        raise DurableRetentionMismatch("MANIFEST_OKX_COUNT")

    ledger_by_period = {item["period"]: item for item in ledger}
    for row in manifest["binance_objects"]:
        path = identity_dir / row["durable_path"]
        if not path.is_file():
            raise DurableRetentionMissing(f"DURABLE_MISSING:{row['durable_path']}")
        data = path.read_bytes()
        digest = sha256_bytes(data)
        if digest != row["sha256"] or len(data) != int(row["byte_length"]):
            raise DurableRetentionMismatch(f"DURABLE_BINANCE:{row['logical_id']}")
        expected = ledger_by_period[row["period"]]
        if digest != expected["local_sha256"] or digest != expected["expected_sha256"]:
            raise DurableRetentionMismatch(
                f"DURABLE_BINANCE_LEDGER:{row['logical_id']}"
            )
        if len(data) != int(expected["byte_size"]):
            raise DurableRetentionMismatch(f"DURABLE_BINANCE_SIZE:{row['logical_id']}")
        cs_path = identity_dir / row["checksum_sidecar_durable_path"]
        if not cs_path.is_file():
            raise DurableRetentionMissing(f"DURABLE_MISSING:{row['checksum_sidecar_durable_path']}")
        named = _parse_checksum_sidecar(cs_path.read_text(encoding="utf-8"), row["original_filename"])
        if named != expected["expected_sha256"]:
            raise DurableRetentionMismatch(f"DURABLE_CHECKSUM:{row['logical_id']}")

    pages_by_index = {int(item["page_index"]): item for item in pages}
    for row in manifest["okx_objects"]:
        path = identity_dir / row["durable_path"]
        if not path.is_file():
            raise DurableRetentionMissing(f"DURABLE_MISSING:{row['durable_path']}")
        data = path.read_bytes()
        digest = sha256_bytes(data)
        if digest != row["sha256"] or len(data) != int(row["byte_length"]):
            raise DurableRetentionMismatch(f"DURABLE_OKX:{row['logical_id']}")
        expected = pages_by_index[int(row["page_id"])]
        if digest != expected["payload_sha256"] or len(data) != int(expected["byte_size"]):
            raise DurableRetentionMismatch(f"DURABLE_OKX_MANIFEST:{row['logical_id']}")
        if dict(row["request"]) != dict(expected["request"]):
            raise DurableRetentionMismatch(f"DURABLE_OKX_REQUEST:{row['logical_id']}")

    inspected = {
        "binance_objects": manifest["binance_objects"],
        "okx_objects": manifest["okx_objects"],
    }
    root_sha = durable_evidence_root_sha256(inspected)
    if root_sha != manifest["durable_evidence_root_sha256"]:
        raise DurableRetentionMismatch("DURABLE_ROOT_SHA256")
    # Authority is the canonical payload, not filesystem listing order.
    shuffled = {
        "binance_objects": list(reversed(manifest["binance_objects"])),
        "okx_objects": list(reversed(manifest["okx_objects"])),
    }
    if durable_evidence_root_sha256(shuffled) != root_sha:
        raise DurableRetentionMismatch("ROOT_NOT_ORDER_INVARIANT")
    return {
        "snapshot_id": SNAPSHOT_ID,
        "durable_evidence_root_sha256": root_sha,
        "binance_objects_retained": BINANCE_OBJECT_COUNT,
        "okx_pages_retained": OKX_PAGE_COUNT,
        "all_preexisting_sha256_match": True,
        "byte_for_byte_recovery_proven": True,
        "offline_recovery_proven": True,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in {"retain", "verify"}:
        print("usage: market_06_durable_retention.py {retain|verify}", file=sys.stderr)
        return 2
    try:
        if args[0] == "retain":
            retain_exact_bytes()
            result = verify_durable_offline()
        else:
            result = verify_durable_offline()
    except DurableRetentionMissing as exc:
        print(f"VERDICT={exc.verdict}:{exc}", file=sys.stderr)
        return 3
    except DurableRetentionMismatch as exc:
        print(f"VERDICT={exc.verdict}:{exc}", file=sys.stderr)
        return 4
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
