"""Materialize only the 2020-01..2024-12 BTCUSDT 1m months for C012.

Does not compute a return. Does not call the full-snapshot acquire path.
A month at or after 2025-01 is rejected before any network fetch.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from scripts.research.core_btc_binance_v0_materializer_lib import (
    ARCHIVE_ROOT_MONTHLY,
    DATASET_ID as SOURCE_DATASET_ID,
    INTERVAL,
    MARKET_TYPE,
    SYMBOL,
    SourceObject,
    acquire_one_object,
    audit_raw_object,
    expected_csv_member_name,
    local_checksum_filename,
    local_zip_filename,
    materialize_object_1m,
    month_bounds_ms,
)
from scripts.research.core_btc_binance_v0_materializer import _sync_get_fetch
from scripts.research.discovery_sprint_03.common import (
    CORE_BTC_ROOT_REL,
    CORE_BTC_SNAPSHOT_ID,
    LEGAL_MONTHS,
    legal_monthly_checksum_key,
    legal_monthly_parquet_path,
    repo_root,
)

ALLOWLIST = LEGAL_MONTHS  # 2020-01 .. 2024-12, 60 months
DENY_FROM = "2025-01"
DISCOVERY_DATASET_ID = "C012_DISCOVERY_BTC_1M_V0"
MANIFEST_REL = "docs/research_data/C012_DISCOVERY_BTC_1M_V0/MANIFEST.json"
_MONTH = re.compile(r"(20\d{2}-\d{2})")


def assert_month_allowed(period: str) -> None:
    if period < "2020-01" or period > "2024-12" or period >= DENY_FROM:
        raise RuntimeError(f"MONTH_REJECTED_BEFORE_BYTE_ACCESS:{period}")


def discovery_objects() -> list[SourceObject]:
    objects = []
    for ym in ALLOWLIST:
        assert_month_allowed(ym)
        objects.append(SourceObject(
            archive_class="monthly",
            source_period=ym,
            source_url=f"{ARCHIVE_ROOT_MONTHLY}/{SYMBOL}/{INTERVAL}/{local_zip_filename(ym)}",
            checksum_url=f"{ARCHIVE_ROOT_MONTHLY}/{SYMBOL}/{INTERVAL}/{local_checksum_filename(ym)}",
            expected_zip_filename=local_zip_filename(ym),
            expected_csv_member_name=expected_csv_member_name(ym),
            period_start_ms=month_bounds_ms(ym)[0],
            period_end_exclusive_ms=month_bounds_ms(ym)[1],
        ))
    if len(objects) != 60:
        raise RuntimeError("ALLOWLIST_COUNT")
    return objects


def guarded_fetch(fetch, url: str):
    found = _MONTH.findall(url)
    if not found:
        raise RuntimeError(f"URL_HAS_NO_MONTH:{url}")
    for period in found:
        assert_month_allowed(period)
    if "2025" in url or "2026" in url:
        raise RuntimeError(f"PROTECTED_URL_REJECTED:{url}")
    return fetch(url)


def structural_month(path: Path, start_ms: int, end_ms: int) -> dict:
    import pyarrow.parquet as pq
    table = pq.read_table(path, columns=["open_time_ms"])
    opens = table.column("open_time_ms").to_pylist()
    if any(int(v) >= int(dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000) for v in opens):
        raise RuntimeError(f"PROTECTED_TIMESTAMP_IN_PARTITION:{path.name}")
    ordered = opens == sorted(opens)
    unique = len(set(opens)) == len(opens)
    expected = (end_ms - start_ms) // 60_000
    return {
        "ROW_COUNT": len(opens),
        "FIRST_OPEN_TIME_MS": int(opens[0]) if opens else None,
        "LAST_OPEN_TIME_MS": int(opens[-1]) if opens else None,
        "TIMESTAMP_ORDERED": ordered,
        "DUPLICATE_OPEN_TIME_COUNT": len(opens) - len(set(opens)),
        "EXPECTED_MINUTES": expected,
        "MISSING_MINUTE_COUNT": expected - len(set(opens)),
        "UNIQUE_TIMESTAMPS": unique,
        "SCHEMA_COLUMNS_READ": ["open_time_ms"],
    }


def snapshot_allowlist_checksums() -> dict[str, str]:
    path = repo_root() / "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
    identity = json.loads(path.read_text())
    payload = identity.get("identity_payload") or identity
    bound = payload.get("snapshot_id") or identity.get("snapshot_id")
    if bound != CORE_BTC_SNAPSHOT_ID:
        raise RuntimeError("SNAPSHOT_ID")
    checksums = payload["output_checksums"]
    return {ym: checksums[legal_monthly_checksum_key(ym)] for ym in ALLOWLIST}


def materialize(root: Path | None = None) -> dict:
    root = root or (repo_root() / CORE_BTC_ROOT_REL)
    fetch = _sync_get_fetch(120.0)
    months = []
    for obj in discovery_objects():
        def one(url, _fetch=fetch):
            return guarded_fetch(_fetch, url)
        acquired = acquire_one_object(root, obj, one, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        if acquired.get("checksum_verification") != "VERIFIED":
            raise RuntimeError(f"ACQUIRE_FAILED:{obj.source_period}:{acquired.get('source_status')}:{acquired.get('checksum_verification')}")
        audited = audit_raw_object(root, obj)
        if audited.get("parser_status") != "OK":
            raise RuntimeError(f"AUDIT_FAILED:{obj.source_period}:{audited.get('parser_status')}")
        made = materialize_object_1m(root, obj, audited)
        if made.get("status") not in ("WROTE", "REUSED_IDENTICAL_PARTITION"):
            raise RuntimeError(f"MATERIALIZE_FAILED:{obj.source_period}:{made.get('status')}")
        path = legal_monthly_parquet_path(root, obj.source_period)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        stats = structural_month(path, obj.period_start_ms, obj.period_end_exclusive_ms)
        months.append({
            "MONTH": obj.source_period,
            "SOURCE_URL": obj.source_url,
            "CHECKSUM_URL": obj.checksum_url,
            "SOURCE_ZIP_SHA256": acquired["local_sha256"],
            "SOURCE_ZIP_BYTES": acquired["byte_size"],
            "CANONICAL_RELATIVE_PATH": f"canonical/1m/monthly/{obj.source_period}.parquet",
            "CANONICAL_SHA256": digest,
            "CANONICAL_CONTENT_SHA256": made.get("canonical_content_sha256"),
            **stats,
        })
    expected = snapshot_allowlist_checksums()
    for row in months:
        row["SNAPSHOT_PARQUET_SHA256"] = expected[row["MONTH"]]
        row["MATCHES_PINNED_SNAPSHOT"] = row["CANONICAL_SHA256"] == expected[row["MONTH"]]
    manifest = _manifest(root, months)
    out = repo_root() / MANIFEST_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def _manifest(root: Path, months: list[dict]) -> dict:
    body = {
        "DATASET_ID": DISCOVERY_DATASET_ID,
        "SOURCE_DATASET_ID": SOURCE_DATASET_ID,
        "SOURCE_SNAPSHOT_ID": CORE_BTC_SNAPSHOT_ID,
        "MARKET": MARKET_TYPE,
        "INSTRUMENT": SYMBOL,
        "RESOLUTION": INTERVAL,
        "START_MONTH": months[0]["MONTH"],
        "END_MONTH": months[-1]["MONTH"],
        "MONTH_COUNT": len(months),
        "TOTAL_ROWS": sum(m["ROW_COUNT"] for m in months),
        "TOTAL_SOURCE_ZIP_BYTES": sum(m["SOURCE_ZIP_BYTES"] for m in months),
        "TOTAL_CANONICAL_BYTES": sum((root / m["CANONICAL_RELATIVE_PATH"]).stat().st_size for m in months),
        "TIMESTAMP_SEMANTICS": "open_time_ms is the UTC open of the 1m bar. The bar closes 60s later. No price column was used to build this manifest.",
        "MISSING_MINUTE_COUNT": sum(m["MISSING_MINUTE_COUNT"] for m in months),
        "DUPLICATE_OPEN_TIME_COUNT": sum(m["DUPLICATE_OPEN_TIME_COUNT"] for m in months),
        "ALL_MATCH_PINNED_SNAPSHOT": all(m["MATCHES_PINNED_SNAPSHOT"] for m in months),
        "MONTHS": months,
        "PROTECTED_2025_MARKET_BYTES_FETCHED": False,
        "PROTECTED_2026_MARKET_BYTES_FETCHED": False,
        "MARKET_DATA_OPENED_FOR_C012": False,
        "MARKET_OUTCOMES_COMPUTED": False,
        "C012_PRIMARY_TEST_EXECUTED": False,
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    body["CANONICAL_MANIFEST_DIGEST"] = digest
    return body


def main() -> int:
    manifest = materialize()
    print(json.dumps({
        "STATUS": "DISCOVERY_MARKET_BYTES_PINNED" if manifest["ALL_MATCH_PINNED_SNAPSHOT"] else "DIGEST_MISMATCH",
        "MONTH_COUNT": manifest["MONTH_COUNT"],
        "TOTAL_ROWS": manifest["TOTAL_ROWS"],
        "MISSING_MINUTE_COUNT": manifest["MISSING_MINUTE_COUNT"],
        "ALL_MATCH_PINNED_SNAPSHOT": manifest["ALL_MATCH_PINNED_SNAPSHOT"],
        "CANONICAL_MANIFEST_DIGEST": manifest["CANONICAL_MANIFEST_DIGEST"],
    }, sort_keys=True))
    return 0 if manifest["ALL_MATCH_PINNED_SNAPSHOT"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
