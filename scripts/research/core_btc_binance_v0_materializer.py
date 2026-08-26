#!/usr/bin/env python3
"""CORE_BTC_BINANCE_V0 deterministic materializer CLI.

Status: `REUSABLE_RESEARCH_TOOL` candidate / `AUDIT_TOOL` until the first
real bulk run (see `scripts/research/README.md`).

Implements the acquisition/materialization pipeline required to eventually
produce `CORE_BTC_BINANCE_V0`. This tool does NOT:

- execute a multi-year download unless the operator explicitly runs
  `--stage acquire` against the frozen plan;
- promote `docs/manifests/CORE_BTC_BINANCE_V0.yaml`;
- authorize hypothesis discovery or forecasting.

One writer per `--dataset-root`. Not distributed-locking. See
`docs/CORE_BTC_BINANCE_V0_MATERIALIZATION_RUNBOOK.md`.
"""
from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.research.core_btc_binance_v0_materializer_lib import (
    AGGREGATION_VERSION,
    CANONICALIZATION_VERSION,
    CHECKSUM_BYTES_ESTIMATE,
    DATASET_ID,
    DEFAULT_DISK_RESERVE_BYTES,
    HTF_SPEC,
    MATERIALIZER_VERSION,
    REPO_MANIFEST_PATH,
    acquire_one_object,
    aggregate_htf,
    assert_disk_budget,
    audit_raw_object,
    build_frozen_source_plan,
    build_snapshot_identity,
    candidate_manifest,
    canonical_1m_path,
    continuity_audit,
    contract_file_sha256,
    dataset_layout,
    disk_usage_for,
    dumps_deterministic,
    estimate_object_bytes,
    file_sha256_if_exists,
    frozen_range_ms,
    gap_extreme_diagnostic,
    htf_path,
    htf_to_parquet_bytes,
    load_all_canonical_1m,
    materialized_size,
    materialize_object_1m,
    merge_cross_object,
    plan_report,
    quality_report_markdown,
    remaining_extracted_csvs,
    retained_raw_size,
    write_json,
)

UTC = timezone.utc
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = Path("artifacts/research_data") / DATASET_ID
STAGES = (
    "plan", "inventory", "acquire", "audit-raw",
    "materialize-1m", "aggregate", "finalize",
)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _detect_git_commit_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(_REPO_ROOT), capture_output=True,
            text=True, timeout=3, check=True)
        sha = result.stdout.strip()
        return sha or "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


async def _aiohttp_fetch(session, url: str, method: str, timeout_seconds: float):
    import aiohttp
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        req = session.head if method == "HEAD" else session.get
        async with req(url, timeout=timeout, allow_redirects=True) as resp:
            length = resp.headers.get("Content-Length")
            cl = int(length) if length and length.isdigit() else None
            if resp.status != 200:
                return None, f"HTTP_{resp.status}", cl
            if method == "HEAD":
                return b"", "HTTP_200", cl
            body = await resp.read()
            return body, "HTTP_200", cl if cl is not None else len(body)
    except aiohttp.ClientError as exc:
        return None, f"NETWORK_ERROR:{exc.__class__.__name__}", None
    except asyncio.TimeoutError:
        return None, "NETWORK_ERROR:Timeout", None


def _sync_get_fetch(timeout_seconds: float):
    """Blocking fetch closure for acquire (GET)."""
    import aiohttp

    async def _one(url: str):
        async with aiohttp.ClientSession() as session:
            return await _aiohttp_fetch(session, url, "GET", timeout_seconds)

    def fetch(url: str):
        return asyncio.run(_one(url))

    return fetch


def _sync_head_fetch(timeout_seconds: float):
    import aiohttp

    async def _one(url: str):
        async with aiohttp.ClientSession() as session:
            return await _aiohttp_fetch(session, url, "HEAD", timeout_seconds)

    def fetch(url: str):
        return asyncio.run(_one(url))

    return fetch


def stage_plan(root: Path, git_sha: str) -> dict:
    objects = build_frozen_source_plan()
    report = plan_report(objects, git_commit_sha=git_sha)
    layout = dataset_layout(root)
    layout["reports"].mkdir(parents=True, exist_ok=True)
    write_json(layout["reports"] / "source_plan.json", report)
    return report


def stage_inventory(root: Path, git_sha: str, head_fetch, timeout_seconds: float) -> dict:
    objects = build_frozen_source_plan()
    rows = []
    total_est = 0
    for obj in objects:
        _body, status, cl = head_fetch(obj.source_url)
        est, origin = estimate_object_bytes(obj.archive_class, cl)
        total_est += est + CHECKSUM_BYTES_ESTIMATE
        rows.append({
            **obj.as_plan_dict(),
            "head_status": status,
            "content_length": cl,
            "estimated_zip_bytes": est,
            "estimate_origin": origin,
        })
    layout = dataset_layout(root)
    usage = disk_usage_for(root)
    budget = {
        "schema_version": 1,
        "report_kind": "CORE_BTC_BINANCE_V0_DISK_BUDGET",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "estimated_raw_download_bytes": total_est,
        "retained_raw_bytes": retained_raw_size(root),
        "materialized_bytes": materialized_size(root),
        "temp_bound_bytes": 8 * 1024 * 1024,
        **usage,
        "objects": rows,
        "note": "HEAD only. Archive bodies are not downloaded in inventory.",
    }
    write_json(layout["reports"] / "disk_budget.json", budget)
    write_json(layout["reports"] / "source_inventory_head.json", {
        "schema_version": 1,
        "objects": rows,
        "source_object_count": len(rows),
    })
    return budget


def stage_acquire(root: Path, git_sha: str, fetch, disk_reserve_bytes: int, budget: Optional[dict]) -> dict:
    objects = build_frozen_source_plan()
    estimated = (budget or {}).get("estimated_raw_download_bytes") or 0
    if estimated == 0:
        estimated = sum(
            estimate_object_bytes(o.archive_class, None)[0] + CHECKSUM_BYTES_ESTIMATE
            for o in objects)
    disk = assert_disk_budget(root, estimated, disk_reserve_bytes=disk_reserve_bytes)
    records = []
    for obj in objects:
        records.append(acquire_one_object(root, obj, fetch, _now_iso()))
    report = {
        "schema_version": 1,
        "report_kind": "CORE_BTC_BINANCE_V0_ACQUIRE",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "disk_safety": disk,
        "objects": records,
        "verified_count": sum(1 for r in records if r.get("checksum_verification") == "VERIFIED"),
        "conflict_count": sum(1 for r in records if r.get("source_status") == "REVISION_CONFLICT"),
    }
    write_json(dataset_layout(root)["reports"] / "acquire_report.json", report)
    return report


def stage_audit_raw(root: Path, git_sha: str) -> dict:
    objects = build_frozen_source_plan()
    records = [audit_raw_object(root, obj) for obj in objects]
    report = {
        "schema_version": 1,
        "report_kind": "CORE_BTC_BINANCE_V0_AUDIT_RAW",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "objects": records,
        "verified_count": sum(1 for r in records if r.get("checksum_verification") == "VERIFIED"),
        "parser_ok_count": sum(1 for r in records if r.get("parser_status") == "OK"),
    }
    write_json(dataset_layout(root)["reports"] / "source_inventory.json", report)
    return report


def stage_materialize_1m(root: Path, git_sha: str, audit_report: Optional[dict] = None) -> dict:
    objects = build_frozen_source_plan()
    if audit_report is None:
        audit_report = stage_audit_raw(root, git_sha)
    by_period = {r["source_period"]: r for r in audit_report["objects"]}
    results = []
    for obj in objects:
        results.append(materialize_object_1m(root, obj, by_period[obj.source_period]))
    leftovers = remaining_extracted_csvs(root)
    report = {
        "schema_version": 1,
        "report_kind": "CORE_BTC_BINANCE_V0_MATERIALIZE_1M",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "partitions": results,
        "extracted_csv_leftovers": leftovers,
        "numeric_representation": (
            "Parquet (zstd). Timestamps and trade_count are int64. OHLC and "
            "volume fields are exact decimal strings produced from Decimal "
            "source parsing (deterministic round-trip). Validation never "
            "uses binary float."
        ),
    }
    write_json(dataset_layout(root)["reports"] / "materialization_report.json", report)
    return report


def stage_aggregate(root: Path, git_sha: str) -> dict:
    objects = build_frozen_source_plan()
    bars, merge_stats = merge_cross_object(load_all_canonical_1m(root, objects))
    start_ms, end_ms = frozen_range_ms()
    summary = {}
    for name, minutes in HTF_SPEC:
        rows = aggregate_htf(bars, minutes, start_ms=start_ms, end_ms=end_ms)
        path = htf_path(root, name)
        from scripts.research.core_btc_binance_v0_materializer_lib import atomic_write_bytes
        atomic_write_bytes(path, htf_to_parquet_bytes(rows))
        incomplete = sum(1 for r in rows if not r.is_complete)
        summary[name] = {
            "expected_buckets": len(rows),
            "complete_buckets": len(rows) - incomplete,
            "incomplete_buckets": incomplete,
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "sha256": file_sha256_if_exists(path),
        }
    report = {
        "schema_version": 1,
        "report_kind": "CORE_BTC_BINANCE_V0_AGGREGATE",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "aggregation_version": AGGREGATION_VERSION,
        "merge": merge_stats,
        "intervals": summary,
        "no_lookahead": (
            "1m available_at = open_time + 60s; HTF available_at = bucket end. "
            "Incomplete HTF buckets have is_complete=false and null aggregates."
        ),
    }
    write_json(dataset_layout(root)["reports"] / "aggregate_report.json", report)
    return report


def stage_finalize(root: Path, git_sha: str) -> dict:
    objects = build_frozen_source_plan()
    inventory_path = dataset_layout(root)["reports"] / "source_inventory.json"
    if inventory_path.exists():
        import json
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))["objects"]
    else:
        inventory = stage_audit_raw(root, git_sha)["objects"]
    bars, merge_stats = merge_cross_object(load_all_canonical_1m(root, objects))
    continuity = continuity_audit(bars)
    extreme = gap_extreme_diagnostic(bars, continuity["gaps"])
    mat_path = dataset_layout(root)["reports"] / "materialization_report.json"
    import json
    mat = json.loads(mat_path.read_text(encoding="utf-8")) if mat_path.exists() else {"partitions": []}
    agg_path = dataset_layout(root)["reports"] / "aggregate_report.json"
    agg = json.loads(agg_path.read_text(encoding="utf-8")) if agg_path.exists() else {"intervals": {}}

    output_checksums = {}
    for obj in objects:
        p = canonical_1m_path(root, obj)
        if p.exists():
            output_checksums[str(p.relative_to(root)).replace("\\", "/")] = file_sha256_if_exists(p)
    for name, _m in HTF_SPEC:
        p = htf_path(root, name)
        output_checksums[str(p.relative_to(root)).replace("\\", "/")] = file_sha256_if_exists(p)

    rejected_schema = sum(p.get("rejected_schema", 0) for p in mat.get("partitions", []))
    rejected_invariant = sum(p.get("rejected_invariant", 0) for p in mat.get("partitions", []))
    conflicting = merge_stats.get("cross_object_conflicting_duplicate_count", 0)
    conflicting += sum(len(p.get("conflicting_duplicate_open_times") or []) for p in mat.get("partitions", []))

    quality = {
        "schema_version": 1,
        "report_kind": "CORE_BTC_BINANCE_V0_QUALITY_REPORT",
        "dataset_id": DATASET_ID,
        "materializer_version": MATERIALIZER_VERSION,
        "provenance_git_commit_sha": git_sha,
        "source_objects_planned": len(objects),
        "source_objects_verified": sum(1 for r in inventory if r.get("checksum_verification") == "VERIFIED"),
        "checksum_failures": sum(
            1 for r in inventory if r.get("checksum_verification") not in ("VERIFIED", "NOT_ATTEMPTED")),
        "continuity": continuity,
        "gap_extreme_diagnostic": extreme,
        "merge": merge_stats,
        "conflicting_duplicate_count": conflicting,
        "rejected_schema": rejected_schema,
        "rejected_invariant": rejected_invariant,
        "htf_incomplete": {
            name: (agg.get("intervals") or {}).get(name, {}).get("incomplete_buckets")
            for name, _m in HTF_SPEC
        },
        "retained_raw_bytes": retained_raw_size(root),
        "materialized_bytes": materialized_size(root),
        "extracted_csv_leftovers": remaining_extracted_csvs(root),
        "discovery_acceptance_gates_satisfied": False,
        "known_limitations": [
            "This report is produced by the materializer. Dataset acceptance "
            "is a later human gate. The repository planning manifest is not "
            "modified.",
            "A non-zero gap count does not automatically invalidate CORE_BTC_BINANCE_V0; "
            "affected HTF buckets are is_complete=false.",
        ],
    }
    from scripts.research.core_btc_binance_v0_materializer_lib import sha256_of_bytes
    quality_bytes = dumps_deterministic({k: v for k, v in quality.items() if k != "snapshot_id"})
    quality_sha = sha256_of_bytes(quality_bytes.encode("utf-8"))
    snapshot = build_snapshot_identity(
        objects=objects,
        inventory=inventory,
        quality_report_sha256=quality_sha,
        output_checksums=output_checksums,
        contract_sha256=contract_file_sha256(_REPO_ROOT),
        git_commit_sha=git_sha,
    )
    quality["snapshot_id"] = snapshot["snapshot_id"]
    quality["quality_report_sha256"] = quality_sha
    layout = dataset_layout(root)
    write_json(layout["reports"] / "quality_report.json", quality)
    from scripts.research.core_btc_binance_v0_materializer_lib import atomic_write_text
    atomic_write_text(layout["reports"] / "quality_report.md", quality_report_markdown(quality))
    write_json(layout["reports"] / "snapshot_manifest.json", snapshot)
    cand = candidate_manifest(snapshot, continuity, inventory, git_sha)
    write_json(layout["manifests"] / "CORE_BTC_BINANCE_V0.candidate.json", cand)
    # Never rewrite the repository planning manifest.
    return {
        "overall_status": "FINALIZE_COMPLETE",
        "snapshot_id": snapshot["snapshot_id"],
        "candidate_manifest_path": "manifests/CORE_BTC_BINANCE_V0.candidate.json",
        "repo_manifest_untouched": REPO_MANIFEST_PATH,
        "discovery_acceptance_gates_satisfied": False,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stage", required=True, choices=[*STAGES, "all"])
    p.add_argument("--dataset-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--timeout-seconds", type=float, default=60.0)
    p.add_argument("--disk-reserve-bytes", type=int, default=DEFAULT_DISK_RESERVE_BYTES)
    p.add_argument("--provenance-git-commit-sha", default=None)
    p.add_argument(
        "--allow-acquire", action="store_true",
        help="required to run --stage acquire / all; refuses accidental bulk download",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    git_sha = args.provenance_git_commit_sha or _detect_git_commit_sha()
    root: Path = args.dataset_root
    dataset_layout(root)["reports"].mkdir(parents=True, exist_ok=True)

    if args.stage in ("acquire", "all") and not args.allow_acquire:
        print(
            "refusing --stage acquire/all without --allow-acquire "
            "(this is the bulk-history safety latch)",
            file=sys.stderr,
        )
        return 2

    if args.stage == "plan":
        report = stage_plan(root, git_sha)
        print(dumps_deterministic({
            "overall_status": "PLAN_COMPLETE",
            "source_object_count": report["source_object_count"],
            "monthly_count": report["monthly_range"]["count"],
            "daily_count": report["daily_range"]["count"],
        }), end="")
        return 0

    if args.stage == "inventory":
        budget = stage_inventory(root, git_sha, _sync_head_fetch(args.timeout_seconds), args.timeout_seconds)
        print(dumps_deterministic({
            "overall_status": "INVENTORY_COMPLETE",
            "estimated_raw_download_bytes": budget["estimated_raw_download_bytes"],
            "free_bytes": budget["free_bytes"],
        }), end="")
        return 0

    if args.stage == "acquire":
        report = stage_acquire(
            root, git_sha, _sync_get_fetch(args.timeout_seconds),
            args.disk_reserve_bytes, None)
        print(dumps_deterministic({
            "overall_status": "ACQUIRE_COMPLETE",
            "verified_count": report["verified_count"],
            "conflict_count": report["conflict_count"],
        }), end="")
        return 0 if report["conflict_count"] == 0 else 1

    if args.stage == "audit-raw":
        report = stage_audit_raw(root, git_sha)
        print(dumps_deterministic({
            "overall_status": "AUDIT_RAW_COMPLETE",
            "verified_count": report["verified_count"],
        }), end="")
        return 0

    if args.stage == "materialize-1m":
        report = stage_materialize_1m(root, git_sha)
        print(dumps_deterministic({
            "overall_status": "MATERIALIZE_1M_COMPLETE",
            "partitions": len(report["partitions"]),
            "extracted_csv_leftovers": report["extracted_csv_leftovers"],
        }), end="")
        return 0 if not report["extracted_csv_leftovers"] else 1

    if args.stage == "aggregate":
        report = stage_aggregate(root, git_sha)
        print(dumps_deterministic({
            "overall_status": "AGGREGATE_COMPLETE",
            "intervals": {k: v["incomplete_buckets"] for k, v in report["intervals"].items()},
        }), end="")
        return 0

    if args.stage == "finalize":
        report = stage_finalize(root, git_sha)
        print(dumps_deterministic(report), end="")
        return 0

    # all
    stage_plan(root, git_sha)
    budget = stage_inventory(root, git_sha, _sync_head_fetch(args.timeout_seconds), args.timeout_seconds)
    stage_acquire(root, git_sha, _sync_get_fetch(args.timeout_seconds), args.disk_reserve_bytes, budget)
    audit = stage_audit_raw(root, git_sha)
    stage_materialize_1m(root, git_sha, audit)
    stage_aggregate(root, git_sha)
    report = stage_finalize(root, git_sha)
    print(dumps_deterministic(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
