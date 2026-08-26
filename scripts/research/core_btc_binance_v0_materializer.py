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

One writer per `--dataset-root` (exclusive lock). See
`docs/CORE_BTC_BINANCE_V0_MATERIALIZATION_RUNBOOK.md`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
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
    DECIMAL_STRING_POLICY,
    DEFAULT_DISK_RESERVE_BYTES,
    HTF_SPEC,
    MATERIALIZER_VERSION,
    REPO_MANIFEST_PATH,
    CoreBtcBinanceV0MaterializerError,
    StagePreconditionError,
    StaleCanonicalPartition,
    acquire_all_verified,
    acquire_one_object,
    aggregate_htf_streaming,
    assert_disk_budget,
    audit_all_verified,
    audit_raw_object,
    build_frozen_source_plan,
    build_snapshot_identity,
    candidate_manifest,
    canonical_1m_path,
    canonical_1m_provenance_path,
    continuity_audit_from_root,
    contract_file_sha256,
    dataset_layout,
    dataset_lock,
    disk_usage_for,
    dumps_deterministic,
    estimate_object_bytes,
    file_sha256_if_exists,
    gap_extreme_diagnostic_streaming,
    htf_path,
    materialized_size,
    materialize_object_1m,
    planned_source_object_count,
    plan_report,
    quality_report_markdown,
    remaining_extracted_csvs,
    require_pyarrow,
    retained_raw_size,
    sha256_of_file,
    verify_canonical_partitions,
    write_json,
)

UTC = timezone.utc
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = Path("artifacts/research_data") / DATASET_ID
STAGES = (
    "plan", "inventory", "acquire", "audit-raw",
    "materialize-1m", "aggregate", "finalize",
)
MUTATING_STAGES = {"acquire", "audit-raw", "materialize-1m", "aggregate", "finalize", "all"}


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
            if cl is not None and cl <= 0:
                cl = None
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
        "schema_version": 2,
        "report_kind": "CORE_BTC_BINANCE_V0_DISK_BUDGET",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "estimated_raw_download_bytes": total_est,
        "retained_raw_bytes": retained_raw_size(root),
        "materialized_bytes": materialized_size(root),
        **usage,
        "objects": rows,
        "note": (
            "HEAD only. Archive bodies are not downloaded in inventory. "
            "Content-Length missing/0/invalid is UNKNOWN and uses a conservative default."
        ),
    }
    write_json(layout["reports"] / "disk_budget.json", budget)
    write_json(layout["reports"] / "source_inventory_head.json", {
        "schema_version": 2,
        "objects": rows,
        "source_object_count": len(rows),
    })
    return budget


def stage_acquire(
    root: Path, git_sha: str, fetch, disk_reserve_bytes: int, budget: Optional[dict],
    allow_zero_reserve: bool = False,
) -> dict:
    objects = build_frozen_source_plan()
    estimated = (budget or {}).get("estimated_raw_download_bytes") or 0
    if estimated == 0:
        estimated = sum(
            estimate_object_bytes(o.archive_class, None)[0] + CHECKSUM_BYTES_ESTIMATE
            for o in objects)
    disk = assert_disk_budget(
        root, estimated, disk_reserve_bytes=disk_reserve_bytes,
        allow_zero_reserve=allow_zero_reserve)
    records = []
    for obj in objects:
        records.append(acquire_one_object(root, obj, fetch, _now_iso()))
    planned = len(objects)
    verified = acquire_all_verified(records, planned)
    report = {
        "schema_version": 2,
        "report_kind": "CORE_BTC_BINANCE_V0_ACQUIRE",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "disk_safety": disk,
        "objects": records,
        "verified_count": sum(1 for r in records if r.get("checksum_verification") == "VERIFIED"),
        "conflict_count": sum(1 for r in records if r.get("source_status") == "REVISION_CONFLICT"),
        "planned_count": planned,
        "acquire_success": verified,
    }
    write_json(dataset_layout(root)["reports"] / "acquire_report.json", report)
    if not verified:
        raise StagePreconditionError(
            "acquire failed: every planned object must be VERIFIED "
            f"(verified={report['verified_count']}/{planned}, "
            f"conflicts={report['conflict_count']})"
        )
    return report


def stage_audit_raw(root: Path, git_sha: str) -> dict:
    objects = build_frozen_source_plan()
    records = [audit_raw_object(root, obj) for obj in objects]
    planned = len(objects)
    ok = audit_all_verified(records, planned)
    report = {
        "schema_version": 2,
        "report_kind": "CORE_BTC_BINANCE_V0_AUDIT_RAW",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "objects": records,
        "verified_count": sum(1 for r in records if r.get("checksum_verification") == "VERIFIED"),
        "parser_ok_count": sum(1 for r in records if r.get("parser_status") == "OK"),
        "planned_count": planned,
        "audit_success": ok,
    }
    write_json(dataset_layout(root)["reports"] / "source_inventory.json", report)
    if not ok:
        raise StagePreconditionError(
            "audit-raw failed: every planned object must be VERIFIED with parser OK "
            f"(verified={report['verified_count']}, parser_ok={report['parser_ok_count']}/{planned})"
        )
    return report


def stage_materialize_1m(root: Path, git_sha: str, audit_report: Optional[dict] = None) -> dict:
    require_pyarrow()
    objects = build_frozen_source_plan()
    if audit_report is None:
        # Always re-audit current bytes; never reuse a stale in-memory report
        # without a fresh on-disk verification inside materialize_object_1m.
        audit_report = {
            "objects": [audit_raw_object(root, obj) for obj in objects],
        }
        if not audit_all_verified(audit_report["objects"], len(objects)):
            raise StagePreconditionError(
                "materialize-1m requires a current VERIFIED audit of all planned objects"
            )
    by_period = {r["source_period"]: r for r in audit_report["objects"]}
    results = []
    for obj in objects:
        rec = by_period.get(obj.source_period)
        if rec is None:
            raise StagePreconditionError(f"audit missing planned period {obj.source_period}")
        results.append(materialize_object_1m(root, obj, rec))
    leftovers = remaining_extracted_csvs(root)
    failed = [r for r in results if r.get("status") not in ("WROTE", "REUSED_IDENTICAL_PARTITION")]
    report = {
        "schema_version": 2,
        "report_kind": "CORE_BTC_BINANCE_V0_MATERIALIZE_1M",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "partitions": results,
        "extracted_csv_leftovers": leftovers,
        "numeric_representation": DECIMAL_STRING_POLICY,
        "materialize_success": not failed and not leftovers,
    }
    write_json(dataset_layout(root)["reports"] / "materialization_report.json", report)
    if leftovers:
        raise StagePreconditionError(f"extracted CSV leftovers are not allowed: {leftovers}")
    if failed:
        raise StagePreconditionError(
            dumps_deterministic({
                "error": "MATERIALIZE_1M_FAILED",
                "failed": [{"source_period": r["source_period"], "status": r.get("status")} for r in failed],
            })
        )
    return report


def stage_aggregate(root: Path, git_sha: str) -> dict:
    require_pyarrow()
    objects = build_frozen_source_plan()
    provenances = verify_canonical_partitions(root, objects)
    summary = aggregate_htf_streaming(root, objects)
    report = {
        "schema_version": 2,
        "report_kind": "CORE_BTC_BINANCE_V0_AGGREGATE",
        "dataset_id": DATASET_ID,
        "provenance_git_commit_sha": git_sha,
        "aggregation_version": AGGREGATION_VERSION,
        "canonical_partitions": len(provenances),
        "intervals": summary,
        "no_lookahead": (
            "1m available_at = open_time + 60s; HTF available_at = bucket end. "
            "Incomplete HTF buckets have is_complete=false and null aggregates."
        ),
        "streaming": True,
    }
    write_json(dataset_layout(root)["reports"] / "aggregate_report.json", report)
    return report


def stage_finalize(root: Path, git_sha: str) -> dict:
    require_pyarrow()
    objects = build_frozen_source_plan()
    inventory = [audit_raw_object(root, obj) for obj in objects]
    if not audit_all_verified(inventory, len(objects)):
        raise StagePreconditionError(
            "finalize requires every planned object currently VERIFIED on disk"
        )
    provenances = verify_canonical_partitions(root, objects)
    agg_path = dataset_layout(root)["reports"] / "aggregate_report.json"
    if not agg_path.exists():
        raise StagePreconditionError("finalize requires aggregate_report.json from a successful aggregate")
    agg = json.loads(agg_path.read_text(encoding="utf-8"))
    for name, _m in HTF_SPEC:
        p = htf_path(root, name)
        if not p.exists():
            raise StagePreconditionError(f"finalize missing HTF output {name}")
        expected = (agg.get("intervals") or {}).get(name, {}).get("sha256")
        actual = sha256_of_file(p)
        if expected != actual:
            raise StagePreconditionError(
                f"HTF {name} sha256 does not match aggregate report"
            )

    continuity = continuity_audit_from_root(root, objects)
    extreme = gap_extreme_diagnostic_streaming(root, objects, continuity["gaps"])
    mat_path = dataset_layout(root)["reports"] / "materialization_report.json"
    mat = json.loads(mat_path.read_text(encoding="utf-8")) if mat_path.exists() else {"partitions": []}

    output_checksums = {}
    for obj in objects:
        p = canonical_1m_path(root, obj)
        output_checksums[str(p.relative_to(root)).replace("\\", "/")] = sha256_of_file(p)
        pp = canonical_1m_provenance_path(root, obj)
        output_checksums[str(pp.relative_to(root)).replace("\\", "/")] = sha256_of_file(pp)
    for name, _m in HTF_SPEC:
        p = htf_path(root, name)
        output_checksums[str(p.relative_to(root)).replace("\\", "/")] = sha256_of_file(p)

    rejected_schema = sum(p.get("rejected_schema", 0) for p in mat.get("partitions", []))
    rejected_invariant = sum(p.get("rejected_invariant", 0) for p in mat.get("partitions", []))
    conflicting = sum(len(p.get("conflicting_duplicate_open_times") or []) for p in mat.get("partitions", []))

    quality = {
        "schema_version": 2,
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
        "canonical_partitions": len(provenances),
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
        "decimal_string_policy": DECIMAL_STRING_POLICY,
        "discovery_acceptance_gates_satisfied": False,
        "known_limitations": [
            "SNAPSHOT_CANDIDATE_READY is not ACCEPTED_FOR_DISCOVERY. "
            "The repository planning manifest is not modified.",
            "A non-zero gap count does not automatically invalidate CORE_BTC_BINANCE_V0; "
            "affected HTF buckets are is_complete=false.",
        ],
    }
    layout = dataset_layout(root)
    quality_path = layout["reports"] / "quality_report.json"
    write_json(quality_path, quality)
    quality_sha = sha256_of_file(quality_path)
    snapshot = build_snapshot_identity(
        objects=objects,
        inventory=inventory,
        quality_report_sha256=quality_sha,
        output_checksums=output_checksums,
        contract_sha256=contract_file_sha256(_REPO_ROOT),
        git_commit_sha=git_sha,
    )
    write_json(layout["reports"] / "snapshot_manifest.json", snapshot)
    from scripts.research.core_btc_binance_v0_materializer_lib import atomic_write_text
    atomic_write_text(
        layout["reports"] / "quality_report.md",
        quality_report_markdown(quality, snapshot["snapshot_id"]),
    )
    cand = candidate_manifest(snapshot, continuity, inventory, git_sha)
    write_json(layout["manifests"] / "CORE_BTC_BINANCE_V0.candidate.json", cand)
    return {
        "overall_status": "SNAPSHOT_CANDIDATE_READY",
        "snapshot_id": snapshot["snapshot_id"],
        "quality_report_sha256": quality_sha,
        "candidate_manifest_path": "manifests/CORE_BTC_BINANCE_V0.candidate.json",
        "repo_manifest_untouched": REPO_MANIFEST_PATH,
        "discovery_acceptance_gates_satisfied": False,
        "research_authorized": False,
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
    p.add_argument(
        "--unsafe-no-disk-reserve", action="store_true",
        help="allow --disk-reserve-bytes 0 (not for normal execution)",
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

    if args.disk_reserve_bytes <= 0 and not args.unsafe_no_disk_reserve:
        print(
            "refusing --disk-reserve-bytes <= 0 without --unsafe-no-disk-reserve",
            file=sys.stderr,
        )
        return 2

    if args.stage in ("materialize-1m", "aggregate", "finalize", "all"):
        try:
            require_pyarrow()
        except CoreBtcBinanceV0MaterializerError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    def _run() -> int:
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
                args.disk_reserve_bytes, None,
                allow_zero_reserve=args.unsafe_no_disk_reserve)
            print(dumps_deterministic({
                "overall_status": "ACQUIRE_COMPLETE",
                "verified_count": report["verified_count"],
                "conflict_count": report["conflict_count"],
            }), end="")
            return 0

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
            return 0

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

        # all — stop immediately on a failed stage
        stage_plan(root, git_sha)
        budget = stage_inventory(root, git_sha, _sync_head_fetch(args.timeout_seconds), args.timeout_seconds)
        stage_acquire(
            root, git_sha, _sync_get_fetch(args.timeout_seconds),
            args.disk_reserve_bytes, budget,
            allow_zero_reserve=args.unsafe_no_disk_reserve)
        audit = stage_audit_raw(root, git_sha)
        stage_materialize_1m(root, git_sha, audit)
        stage_aggregate(root, git_sha)
        report = stage_finalize(root, git_sha)
        print(dumps_deterministic(report), end="")
        return 0

    try:
        if args.stage in MUTATING_STAGES:
            with dataset_lock(root):
                return _run()
        return _run()
    except StaleCanonicalPartition as exc:
        print(str(exc), file=sys.stderr)
        print(dumps_deterministic({
            "overall_status": "STALE_CANONICAL_PARTITION",
            "error": str(exc)[:2000],
        }), end="")
        return 1
    except StagePreconditionError as exc:
        print(str(exc), file=sys.stderr)
        print(dumps_deterministic({
            "overall_status": "STAGE_PRECONDITION_FAILED",
            "error": str(exc)[:2000],
        }), end="")
        return 1
    except CoreBtcBinanceV0MaterializerError as exc:
        print(str(exc), file=sys.stderr)
        print(dumps_deterministic({
            "overall_status": "MATERIALIZER_ERROR",
            "error": str(exc)[:2000],
        }), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
