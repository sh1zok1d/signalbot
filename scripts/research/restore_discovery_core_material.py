"""Restore CORE BTC/ETH 2020-2024 legal development material.

Infrastructure only. No discovery gates, thresholds, nulls, or evaluation.
Downloads only frozen 2020-01..2024-12 source objects. Refuses 2025/2026 URLs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping

from scripts.research.core_btc_binance_v0_materializer_lib import (
    SourceObject,
    audit_raw_object,
    canonical_1m_path,
    materialize_object_1m,
    raw_checksum_path,
    raw_zip_path,
    require_pyarrow,
)
from scripts.research.core_btc_binance_v0_probe_lib import ARCHIVE_ROOT, sha256_of_bytes
from scripts.research.market05_eth_execution_binding import (
    ETH_PARQUET_ROOT_REL,
    ETH_SNAPSHOT_ID,
    ETH_ZIP_ROOT_REL,
    development_objects,
    load_accepted_eth_snapshot,
    load_execution_binding,
    materialize_one_object,
    sha256_file,
)


REPO = Path(__file__).resolve().parents[2]
BTC_INVENTORY_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SOURCE_INVENTORY_717d37a4.json"
BTC_SNAPSHOT_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
BTC_ROOT_REL = "artifacts/research_data/CORE_BTC_BINANCE_V0"
BTC_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
LEGAL_END_EXCLUSIVE = "2025-01"
USER_AGENT = "signalbot-discovery-core-restore/1.0"
BTC_SUCCESS_STATUSES = {"WROTE", "REUSED_IDENTICAL_PARTITION"}
HTTP_RETRIES = 4


class RestoreError(RuntimeError):
    """Restoration failed closed."""


def period_is_protected(period: str) -> bool:
    text = str(period)
    return (
        text >= LEGAL_END_EXCLUSIVE
        or "2025-" in text
        or "2026-" in text
        or text.startswith("2025")
        or text.startswith("2026")
    )


def assert_url_legal(url: str) -> None:
    if "2025-" in url or "2026-" in url:
        raise RestoreError(f"PROTECTED_URL_REFUSED:{url}")


def http_get(url: str) -> bytes:
    assert_url_legal(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None
    for attempt in range(HTTP_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise RestoreError(f"HTTP_{exc.code}:{url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RestoreError(f"URL_ERROR:{url}:{last}") from last


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_btc_legal_inventory(repo: Path) -> list[dict[str, Any]]:
    payload = json.loads((repo / BTC_INVENTORY_REL).read_text(encoding="utf-8"))
    selected: list[dict[str, Any]] = []
    for obj in payload.get("objects") or []:
        period = str(obj.get("source_period") or "")
        if obj.get("archive_class") != "monthly":
            continue
        if period_is_protected(period):
            continue
        if period < "2020-01" or period > "2024-12":
            continue
        selected.append(obj)
    if len(selected) != 60:
        raise RestoreError(f"BTC_LEGAL_OBJECT_COUNT:{len(selected)}")
    for obj in selected:
        assert_url_legal(str(obj["source_url"]))
        if period_is_protected(str(obj["source_period"])):
            raise RestoreError(f"PROTECTED_PERIOD:{obj['source_period']}")
    return selected


def btc_output_checksums(repo: Path) -> dict[str, str]:
    snapshot = json.loads((repo / BTC_SNAPSHOT_REL).read_text(encoding="utf-8"))
    payload = snapshot.get("identity_payload") or snapshot
    bound = payload.get("snapshot_id") or snapshot.get("snapshot_id")
    if bound != BTC_SNAPSHOT_ID:
        raise RestoreError(f"BTC_SNAPSHOT_MISMATCH:{bound}")
    checksums = payload.get("output_checksums") or {}
    return {str(k): str(v) for k, v in checksums.items()}


def source_object_from_inventory(obj: Mapping[str, Any]) -> SourceObject:
    period = str(obj["source_period"])
    if period_is_protected(period):
        raise RestoreError(f"PROTECTED_PERIOD:{period}")
    url = str(obj["source_url"])
    assert_url_legal(url)
    return SourceObject(
        archive_class="monthly",
        source_period=period,
        source_url=url,
        checksum_url=str(obj.get("checksum_url") or ""),
        expected_zip_filename=str(obj["expected_zip_filename"]),
        expected_csv_member_name=str(obj["expected_csv_member_name"]),
        period_start_ms=int(obj["period_start_ms"]),
        period_end_exclusive_ms=int(obj["period_end_exclusive_ms"]),
    )


def restore_btc(repo: Path, *, workers: int = 8) -> dict[str, Any]:
    require_pyarrow()
    root = repo / BTC_ROOT_REL
    root.mkdir(parents=True, exist_ok=True)
    inventory = load_btc_legal_inventory(repo)
    checksums = btc_output_checksums(repo)
    downloaded = 0
    verified = 0
    reused = 0

    def _one(obj: dict[str, Any]) -> tuple[str, bytes, str, bool]:
        period = str(obj["source_period"])
        expected = str(obj.get("expected_sha256") or obj.get("local_sha256"))
        src = source_object_from_inventory(obj)
        zip_path = raw_zip_path(root, src)
        if zip_path.is_file() and sha256_of_bytes(zip_path.read_bytes()) == expected:
            return period, zip_path.read_bytes(), expected, True
        data = http_get(str(obj["source_url"]))
        digest = sha256_bytes(data)
        if digest != expected:
            raise RestoreError(f"BTC_ZIP_SHA256_MISMATCH:{period}:{digest}")
        return period, data, expected, False

    blobs: dict[str, tuple[bytes, str, dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_one, obj): obj for obj in inventory}
        for fut in as_completed(futures):
            period, data, expected, was_reuse = fut.result()
            blobs[period] = (data, expected, futures[fut])
            verified += 1
            if was_reuse:
                reused += 1
            else:
                downloaded += 1

    materialized = 0
    matched = 0
    for obj in inventory:
        period = str(obj["source_period"])
        data, expected, raw_obj = blobs[period]
        src = source_object_from_inventory(raw_obj)
        zip_path = raw_zip_path(root, src)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        if not zip_path.is_file() or sha256_of_bytes(zip_path.read_bytes()) != expected:
            zip_path.write_bytes(data)
        sidecar = raw_checksum_path(root, src)
        sidecar.write_text(f"{expected}  {src.expected_zip_filename}\n", encoding="utf-8")
        audit = audit_raw_object(root, src)
        result = materialize_object_1m(root, src, audit)
        if result.get("status") not in BTC_SUCCESS_STATUSES:
            raise RestoreError(f"BTC_MATERIALIZE_FAIL:{period}:{result.get('status')}")
        parquet_path = canonical_1m_path(root, src)
        rel = f"canonical/1m/monthly/{period}.parquet"
        expected_parquet = checksums.get(rel)
        if expected_parquet is None:
            raise RestoreError(f"BTC_PARQUET_CHECKSUM_UNBOUND:{rel}")
        actual = sha256_of_bytes(parquet_path.read_bytes())
        if actual != expected_parquet:
            raise RestoreError(f"BTC_PARQUET_SHA256_MISMATCH:{period}:{actual}")
        materialized += 1
        matched += 1
    return {
        "BTC_SOURCE_OBJECTS_DOWNLOADED": downloaded,
        "BTC_SOURCE_OBJECTS_REUSED": reused,
        "BTC_SOURCE_OBJECTS_VERIFIED": verified,
        "BTC_PARQUETS_MATERIALIZED": materialized,
        "BTC_PARQUETS_HASH_MATCHED": matched,
    }


def eth_zip_url(filename: str) -> str:
    if period_is_protected(filename):
        raise RestoreError(f"PROTECTED_FILENAME:{filename}")
    url = f"{ARCHIVE_ROOT}/ETHUSDT/1m/{filename}"
    assert_url_legal(url)
    return url


def restore_eth(repo: Path, *, workers: int = 8) -> dict[str, Any]:
    require_pyarrow()
    snapshot = load_accepted_eth_snapshot(repo)
    if snapshot.get("snapshot_id") != ETH_SNAPSHOT_ID:
        raise RestoreError(f"ETH_SNAPSHOT_MISMATCH:{snapshot.get('snapshot_id')}")
    objects = development_objects(snapshot)
    if len(objects) != 60:
        raise RestoreError(f"ETH_LEGAL_OBJECT_COUNT:{len(objects)}")
    for obj in objects:
        period = str(obj["source_period"])
        if period_is_protected(period) or period < "2020-01" or period > "2024-12":
            raise RestoreError(f"ETH_ILLEGAL_PERIOD:{period}")
        assert_url_legal(eth_zip_url(str(obj["expected_zip_filename"])))
    binding = load_execution_binding(repo)
    bound_by_period = {str(item["source_period"]): item for item in binding["objects"]}
    if len(bound_by_period) != 60:
        raise RestoreError(f"ETH_BINDING_OBJECT_COUNT:{len(bound_by_period)}")
    zip_root = repo / ETH_ZIP_ROOT_REL
    parquet_root = repo / ETH_PARQUET_ROOT_REL
    zip_root.mkdir(parents=True, exist_ok=True)
    (parquet_root / "canonical" / "1m" / "monthly").mkdir(parents=True, exist_ok=True)

    downloaded = 0
    verified = 0
    reused = 0

    def _one(obj: dict[str, Any]) -> bool:
        period = str(obj["source_period"])
        if period_is_protected(period):
            raise RestoreError(f"PROTECTED_PERIOD:{period}")
        filename = str(obj["expected_zip_filename"])
        expected = str(obj["zip_sha256"])
        dest = zip_root / filename
        if dest.is_file() and sha256_file(dest) == expected:
            return True
        data = http_get(eth_zip_url(filename))
        digest = sha256_bytes(data)
        if digest != expected:
            raise RestoreError(f"ETH_ZIP_SHA256_MISMATCH:{period}:{digest}")
        dest.write_bytes(data)
        return False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, obj) for obj in objects]
        for fut in as_completed(futures):
            was_reuse = fut.result()
            verified += 1
            if was_reuse:
                reused += 1
            else:
                downloaded += 1

    materialized = 0
    matched = 0
    for obj in objects:
        period = str(obj["source_period"])
        record = materialize_one_object(
            obj, repo=repo, zip_root=zip_root, parquet_root=parquet_root
        )
        expected_parquet = str(bound_by_period[period]["canonical_parquet_sha256"])
        dest = parquet_root / record["canonical_parquet_relative_path"]
        actual = sha256_file(dest)
        if actual != expected_parquet:
            raise RestoreError(f"ETH_PARQUET_SHA256_MISMATCH:{period}:{actual}")
        if record["canonical_parquet_sha256"] != expected_parquet:
            raise RestoreError(f"ETH_PARQUET_RECORD_MISMATCH:{period}")
        materialized += 1
        matched += 1
    return {
        "ETH_SOURCE_OBJECTS_DOWNLOADED": downloaded,
        "ETH_SOURCE_OBJECTS_REUSED": reused,
        "ETH_SOURCE_OBJECTS_VERIFIED": verified,
        "ETH_PARQUETS_MATERIALIZED": materialized,
        "ETH_PARQUETS_HASH_MATCHED": matched,
    }


def restore_all(repo: Path | None = None, *, workers: int = 8) -> dict[str, Any]:
    base = repo or REPO
    report = {
        "REQUESTED_2025_OBJECTS": 0,
        "REQUESTED_2026_OBJECTS": 0,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "NEW_SNAPSHOT_IDENTITY_CREATED": False,
        "BTC_SNAPSHOT_ID": BTC_SNAPSHOT_ID,
        "ETH_SNAPSHOT_ID": ETH_SNAPSHOT_ID,
    }
    report.update(restore_btc(base, workers=workers))
    report.update(restore_eth(base, workers=workers))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    payload = restore_all(workers=args.workers)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except RestoreError as exc:
        print(f"RESTORE_FAILED:{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
