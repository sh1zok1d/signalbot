"""Materialize MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0.

Wraps the already-acquired Binance REST funding JSONL. Does not fetch
protected 2025/2026 OOS, does not use B2-06 as authority, and does not
run EmaCross/EmaCrossFunding or any strategy transform.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

from scripts.research.market_03_binance_um_btcusdt_fundingrate_rest_v0_lib import (
    ACQUISITION_COMPATIBILITY_RELATIVE_PATH,
    DATASET_ID,
    ENDPOINT_PATH,
    ENDPOINT_USED,
    EXPECTED_FIRST_FUNDINGTIME_UTC,
    EXPECTED_LAST_FUNDINGTIME_UTC,
    EXPECTED_ROW_COUNT,
    EXPECTED_SOURCE_SHA256,
    EXPECTED_SOURCE_SIZE,
    MARKET_TYPE,
    PRE_SNAPSHOT_HEAD,
    PRE_SNAPSHOT_TREE,
    PRIMARY_ENDPOINT,
    PREREG_JSON_SHA256,
    PREREG_MD_SHA256,
    PROVIDER,
    REPRODUCTION_FUNDINGTIME_ASSUMPTION,
    REPRODUCTION_FUNDINGTIME_ASSUMPTION_MEANING,
    REQUEST_START_INCLUSIVE,
    SOURCE_RELATIVE_PATH,
    SPOT_DATA_SHA256,
    SPOT_DATASET_ID,
    SPOT_SNAPSHOT_ID,
    STRICT_HISTORICAL_PUBLICATION_LATENCY,
    SYMBOL,
    VENUE,
    Market03FundingSnapshotError,
    assert_no_strategy_quantities,
    audit_funding_rows,
    build_funding_identity_payload,
    canonical_jsonl_bytes,
    construction_code_hashes,
    dumps_deterministic,
    load_acquisition_rest_provenance,
    parse_rest_funding_jsonl,
    prove_source_fidelity,
    refuse_b2_06_as_authority,
    sha256_of_bytes,
    sha256_of_file,
    snapshot_from_payload,
    verify_source_file,
)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_deterministic(payload), encoding="utf-8")


def verify_spot_and_prereg_unchanged(repo_root: Path) -> dict[str, bool]:
    spot_snap = (
        repo_root
        / "docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
        / "SNAPSHOT_2ce1f504.json"
    )
    import json

    snapshot = json.loads(spot_snap.read_text(encoding="utf-8"))
    if snapshot["snapshot_id"] != SPOT_SNAPSHOT_ID:
        raise Market03FundingSnapshotError("spot SNAPSHOT_ID changed")
    payload = snapshot["identity_payload"]
    if payload["dataset_id"] != SPOT_DATASET_ID:
        raise Market03FundingSnapshotError("spot DATASET_ID changed")
    if payload["canonical_klines_sha256"] != SPOT_DATA_SHA256:
        raise Market03FundingSnapshotError("spot DATA SHA256 changed")
    prereg_md = repo_root / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
    prereg_js = repo_root / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
    if sha256_of_file(prereg_md) != PREREG_MD_SHA256:
        raise Market03FundingSnapshotError("prereg MD SHA256 changed; FAIL CLOSED")
    if sha256_of_file(prereg_js) != PREREG_JSON_SHA256:
        raise Market03FundingSnapshotError("prereg JSON SHA256 changed; FAIL CLOSED")
    return {
        "SPOT_SNAPSHOT_UNCHANGED": True,
        "PREREG_UNCHANGED": True,
    }


def evidence_readme(snapshot_id: str, hashes: dict[str, str], quality: dict[str, Any]) -> str:
    short = snapshot_id[:8]
    return (
        f"# {DATASET_ID} snapshot evidence\n\n"
        f"**Status:** `SNAPSHOT_MATERIALIZED_PRE_ARM`\n"
        f"**Snapshot ID:** `{snapshot_id}`\n"
        f"**Construction parent commit:** `{PRE_SNAPSHOT_HEAD}`\n\n"
        "Dedicated Binance USD-M `BTCUSDT` REST `/fapi/v1/fundingRate` identity "
        "for MARKET-03. Not B2-06. Not a strategy result. Not ARM.\n\n"
        "Raw REST JSONL and canonical JSONL are gitignored. This snapshot proves "
        "exact historical identity at materialization time.\n\n"
        "| Archival file | Runtime source | SHA-256 |\n"
        "|---|---|---|\n"
        f"| `SNAPSHOT_{short}.json` | `reports/snapshot_manifest.json` | `{hashes['SNAPSHOT']}` |\n"
        f"| `SOURCE_LEDGER_{short}.json` | `reports/source_ledger.json` | `{hashes['SOURCE_LEDGER']}` |\n"
        f"| `QUALITY_REPORT_{short}.json` | `reports/quality_report.json` | `{hashes['QUALITY_REPORT']}` |\n\n"
        "Authorized REST window `[2019-09-01T00:00:00Z, 2025-01-01T00:00:00Z)`:\n\n"
        f"- {quality['row_count']} raw funding rows\n"
        f"- first fundingTime `{quality['first_fundingTime_utc']}`\n"
        f"- last fundingTime `{quality['last_fundingTime_utc']}`\n"
        f"- duplicate fundingTime: {quality['duplicate_fundingTime_count']}\n"
        f"- missing expected 8h hour-floor events: "
        f"{quality['missing_expected_8h_hour_floor_count']}\n"
        f"- canonical JSONL SHA256 `{quality['canonical_funding_sha256']}`\n\n"
        "```text\n"
        f"STRICT_HISTORICAL_PUBLICATION_LATENCY = {STRICT_HISTORICAL_PUBLICATION_LATENCY}\n"
        f"REPRODUCTION_FUNDINGTIME_ASSUMPTION   = {REPRODUCTION_FUNDINGTIME_ASSUMPTION}\n"
        "```\n\n"
        "Durability: `IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED`.\n\n"
        f"Canonical repository manifest: `docs/manifests/{DATASET_ID}.yaml`.\n"
        "Provenance record: `docs/research/MARKET_03_FUNDING_SNAPSHOT.md`.\n"
    )


def run_materialization(
    *,
    repo_root: Path,
    dataset_root: Path,
    source_path: Path,
    emit_docs: bool,
) -> dict[str, Any]:
    assert_no_strategy_quantities(dir())
    refuse_b2_06_as_authority(None)
    integrity = verify_spot_and_prereg_unchanged(repo_root)
    rest_prov = load_acquisition_rest_provenance(repo_root)
    source_info = verify_source_file(source_path)
    source_bytes = source_path.read_bytes()
    if sha256_of_bytes(source_bytes) != EXPECTED_SOURCE_SHA256:
        raise Market03FundingSnapshotError("in-memory source digest mismatch")
    rows = parse_rest_funding_jsonl(source_bytes.decode("utf-8"))
    if len(rows) != EXPECTED_ROW_COUNT:
        raise Market03FundingSnapshotError(
            f"row count {len(rows)} != frozen {EXPECTED_ROW_COUNT}"
        )
    canonical_bytes = canonical_jsonl_bytes(rows)
    fidelity = prove_source_fidelity(rows, canonical_bytes)
    canonical_sha = sha256_of_bytes(canonical_bytes)
    if canonical_sha != EXPECTED_SOURCE_SHA256:
        raise Market03FundingSnapshotError(
            "identity normalization changed REST JSONL bytes"
        )
    if canonical_bytes != source_bytes:
        raise Market03FundingSnapshotError(
            "canonical bytes are not an identity copy of the source JSONL"
        )
    quality = audit_funding_rows(rows)
    if quality["first_fundingTime_utc"] != EXPECTED_FIRST_FUNDINGTIME_UTC:
        raise Market03FundingSnapshotError("first fundingTime drifted from acquisition")
    if quality["last_fundingTime_utc"] != EXPECTED_LAST_FUNDINGTIME_UTC:
        raise Market03FundingSnapshotError("last fundingTime drifted from acquisition")
    if quality["protected_oos_row_count"] != 0:
        raise Market03FundingSnapshotError("protected OOS present")
    if quality["duplicate_fundingTime_count"] != 0:
        raise Market03FundingSnapshotError("duplicate fundingTime present")
    if quality["conflicting_duplicate_fundingTime_count"] != 0:
        raise Market03FundingSnapshotError("conflicting duplicates present")
    if quality["non_finite_rate_count"] != 0:
        raise Market03FundingSnapshotError("non-finite fundingRate present")
    if not quality["chronological_strictly_increasing"]:
        raise Market03FundingSnapshotError("fundingTime is not strictly increasing")
    quality["canonical_funding_sha256"] = canonical_sha
    quality["canonical_bytes"] = len(canonical_bytes)
    quality["source_bytes"] = len(source_bytes)
    quality["fidelity"] = fidelity
    quality["dataset_id"] = DATASET_ID
    quality["protected_oos_used_for_science"] = False
    quality["strategy_quantities_computed"] = False
    quality["b2_06_used_as_authority"] = False
    quality["strict_historical_publication_latency"] = (
        STRICT_HISTORICAL_PUBLICATION_LATENCY
    )
    quality["reproduction_fundingtime_assumption"] = (
        REPRODUCTION_FUNDINGTIME_ASSUMPTION
    )
    quality["reproduction_fundingtime_assumption_meaning"] = (
        REPRODUCTION_FUNDINGTIME_ASSUMPTION_MEANING
    )
    quality["publication_latency_not_upgraded"] = True
    quality["fundingtime_not_legal_available_at"] = True

    construction = construction_code_hashes(repo_root)
    identity_payload = build_funding_identity_payload(
        canonical_funding_sha256=canonical_sha,
        canonical_row_count=quality["row_count"],
        first_fundingTime_utc=quality["first_fundingTime_utc"],
        last_fundingTime_utc=quality["last_fundingTime_utc"],
        duplicate_fundingTime_count=quality["duplicate_fundingTime_count"],
        missing_expected_8h_count=quality["missing_expected_8h_hour_floor_count"],
        construction_code_sha256=construction,
        source_sha256=source_info["sha256"],
        source_size=source_info["size"],
        source_relative_path=SOURCE_RELATIVE_PATH,
        rest_provenance=rest_prov,
    )
    snapshot = snapshot_from_payload(identity_payload)
    snapshot_id = snapshot["snapshot_id"]
    quality["snapshot_id"] = snapshot_id

    source_ledger = {
        "dataset_id": DATASET_ID,
        "snapshot_id": snapshot_id,
        "b2_06_is_not_market_03_authority": True,
        "source": {
            "class": "BINANCE_UM_FUNDINGRATE_REST_JSONL",
            "relative_path": SOURCE_RELATIVE_PATH,
            "resolved_path": str(source_path),
            "sha256": source_info["sha256"],
            "size_bytes": source_info["size"],
            "endpoint": PRIMARY_ENDPOINT,
            "endpoint_used": ENDPOINT_USED,
            "endpoint_path": ENDPOINT_PATH,
            "symbol": SYMBOL,
            "market_type": MARKET_TYPE,
            "provider": PROVIDER,
            "venue": VENUE,
            "retrieval_timestamp_utc": rest_prov.get("retrieval_timestamp_utc"),
            "request_startTime_ms": rest_prov.get("startTime_ms"),
            "request_endTime_exclusive_ms": rest_prov.get("endTime_exclusive_ms"),
            "request_start_inclusive": REQUEST_START_INCLUSIVE,
            "request_end_exclusive": "2025-01-01T00:00:00Z",
            "limit": rest_prov.get("limit"),
            "pages": rest_prov.get("pages"),
            "fallback_endpoint_used": rest_prov.get("fallback_endpoint_used"),
            "primary_endpoint_http_status": rest_prov.get("primary_endpoint_http_status"),
            "user_agent": rest_prov.get("user_agent"),
            "acquisition_compatibility_record": ACQUISITION_COMPATIBILITY_RELATIVE_PATH,
        },
        "normalized": {
            "relative_path": f"artifacts/research_data/{DATASET_ID}/canonical/BTCUSDT_UM_fundingRate.jsonl",
            "sha256": canonical_sha,
            "bytes": len(canonical_bytes),
            "row_count": quality["row_count"],
            "identity_copy_of_source": True,
        },
        "spot_authority_unchanged": {
            "dataset_id": SPOT_DATASET_ID,
            "snapshot_id": SPOT_SNAPSHOT_ID,
            "spot_data_sha256": SPOT_DATA_SHA256,
        },
        "prereg_unchanged": {
            "md_sha256": PREREG_MD_SHA256,
            "json_sha256": PREREG_JSON_SHA256,
        },
        "strict_historical_publication_latency": STRICT_HISTORICAL_PUBLICATION_LATENCY,
        "reproduction_fundingtime_assumption": REPRODUCTION_FUNDINGTIME_ASSUMPTION,
        "protected_oos_excluded": True,
        "strategy_executed": False,
        "outcomes_inspected": False,
        "parameter_search": False,
        "armed": False,
        "canonical_executions_authorized": 0,
        "canonical_executions_consumed": 0,
    }

    raw_dir = dataset_root / "raw"
    canonical_dir = dataset_root / "canonical"
    reports_dir = dataset_root / "reports"
    for path in (raw_dir, canonical_dir, reports_dir):
        path.mkdir(parents=True, exist_ok=True)
    raw_copy = raw_dir / "BTCUSDT_UM_fundingRate_rest_authorized.jsonl"
    canonical_path = canonical_dir / "BTCUSDT_UM_fundingRate.jsonl"
    raw_copy.write_bytes(source_bytes)
    canonical_path.write_bytes(canonical_bytes)
    if sha256_of_file(raw_copy) != EXPECTED_SOURCE_SHA256:
        raise Market03FundingSnapshotError("dedicated raw copy digest mismatch")
    if sha256_of_file(canonical_path) != canonical_sha:
        raise Market03FundingSnapshotError("dedicated canonical digest mismatch")

    write_json(reports_dir / "snapshot_manifest.json", snapshot)
    write_json(reports_dir / "source_ledger.json", source_ledger)
    write_json(reports_dir / "quality_report.json", quality)

    hashes = {
        "SNAPSHOT": sha256_of_file(reports_dir / "snapshot_manifest.json"),
        "SOURCE_LEDGER": sha256_of_file(reports_dir / "source_ledger.json"),
        "QUALITY_REPORT": sha256_of_file(reports_dir / "quality_report.json"),
    }

    if emit_docs:
        docs_dir = repo_root / "docs" / "research_data" / DATASET_ID
        docs_dir.mkdir(parents=True, exist_ok=True)
        short = snapshot_id[:8]
        write_json(docs_dir / f"SNAPSHOT_{short}.json", snapshot)
        write_json(docs_dir / f"SOURCE_LEDGER_{short}.json", source_ledger)
        write_json(docs_dir / f"QUALITY_REPORT_{short}.json", quality)
        (docs_dir / "README.md").write_text(
            evidence_readme(snapshot_id, hashes, quality),
            encoding="utf-8",
        )
        hashes = {
            "SNAPSHOT": sha256_of_file(docs_dir / f"SNAPSHOT_{short}.json"),
            "SOURCE_LEDGER": sha256_of_file(docs_dir / f"SOURCE_LEDGER_{short}.json"),
            "QUALITY_REPORT": sha256_of_file(docs_dir / f"QUALITY_REPORT_{short}.json"),
        }
        (docs_dir / "README.md").write_text(
            evidence_readme(snapshot_id, hashes, quality),
            encoding="utf-8",
        )

    result = {
        "dataset_id": DATASET_ID,
        "snapshot_id": snapshot_id,
        "source_sha256": source_info["sha256"],
        "source_size": source_info["size"],
        "funding_data_sha256": canonical_sha,
        "funding_rows": quality["row_count"],
        "first_fundingTime_utc": quality["first_fundingTime_utc"],
        "last_fundingTime_utc": quality["last_fundingTime_utc"],
        "duplicates": quality["duplicate_fundingTime_count"],
        "missing_expected_8h_hour_floor_count": quality[
            "missing_expected_8h_hour_floor_count"
        ],
        "anomalies": quality["anomalies"],
        "identity_hashes": hashes,
        "construction_code_sha256": construction,
        "SPOT_SNAPSHOT_UNCHANGED": integrity["SPOT_SNAPSHOT_UNCHANGED"],
        "PREREG_UNCHANGED": integrity["PREREG_UNCHANGED"],
        "STRICT_HISTORICAL_PUBLICATION_LATENCY": STRICT_HISTORICAL_PUBLICATION_LATENCY,
        "REPRODUCTION_FUNDINGTIME_ASSUMPTION": REPRODUCTION_FUNDINGTIME_ASSUMPTION,
        "MARKET_03_STRATEGY_EXECUTED": False,
        "MARKET_03_OUTCOMES_INSPECTED": False,
        "MARKET_03_PARAMETER_SEARCH": False,
        "MARKET_03_ARMED": False,
        "CANONICAL_EXECUTIONS_AUTHORIZED": 0,
        "CANONICAL_EXECUTIONS_CONSUMED": 0,
        "PROTECTED_OOS_TOUCHED": False,
        "pre_snapshot_head": PRE_SNAPSHOT_HEAD,
        "pre_snapshot_tree": PRE_SNAPSHOT_TREE,
        "prereg_md_sha256": PREREG_MD_SHA256,
        "prereg_json_sha256": PREREG_JSON_SHA256,
    }
    write_json(reports_dir / "materialization_result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize MARKET-03 dedicated REST funding snapshot"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("artifacts/research_data") / DATASET_ID,
    )
    parser.add_argument(
        "--source-path",
        type=Path,
        default=None,
        help="REST JSONL path; defaults to the acquisition canonical file",
    )
    parser.add_argument("--allow-materialize", action="store_true")
    parser.add_argument("--emit-docs", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.allow_materialize:
        print("refusing materialization without --allow-materialize", file=sys.stderr)
        return 2
    repo_root = args.repo_root.resolve()
    source_path = (
        args.source_path.resolve()
        if args.source_path is not None
        else repo_root / SOURCE_RELATIVE_PATH
    )
    dataset_root = args.dataset_root
    if not dataset_root.is_absolute():
        dataset_root = repo_root / dataset_root
    try:
        result = run_materialization(
            repo_root=repo_root,
            dataset_root=dataset_root,
            source_path=source_path,
            emit_docs=args.emit_docs,
        )
    except Market03FundingSnapshotError as exc:
        print(f"FUNDING SNAPSHOT FAILED: {exc}", file=sys.stderr)
        return 1
    print(
        dumps_deterministic(
            {
                "dataset_id": result["dataset_id"],
                "snapshot_id": result["snapshot_id"],
                "source_sha256": result["source_sha256"],
                "source_size": result["source_size"],
                "funding_data_sha256": result["funding_data_sha256"],
                "funding_rows": result["funding_rows"],
                "first_fundingTime_utc": result["first_fundingTime_utc"],
                "last_fundingTime_utc": result["last_fundingTime_utc"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
