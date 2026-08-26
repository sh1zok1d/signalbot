#!/usr/bin/env python3
"""CORE_BTC_BINANCE_V0 deterministic source-capability probe.

Status: `AUDIT_TOOL` (see `scripts/research/README.md`).

This is research infrastructure, not the multi-year materializer. It exists
to prove or falsify the basic source assumptions behind `CORE_BTC_BINANCE_V0`
(docs/CORE_BTC_BINANCE_V0_CONTRACT.md, docs/manifests/CORE_BTC_BINANCE_V0.yaml)
on a small, fixed set of historical months before any bulk acquisition is
attempted.

It never performs a multi-year backfill, never touches forecasting/V1/V2/E1
semantics, never touches production ingestion/runtime/config, and never
marks the dataset manifest as accepted -- see
`docs/CORE_BTC_BINANCE_V0_PROBE_RUNBOOK.md`.

Three modes:

    --mode inventory     print/write the exact source URLs; no network
    --mode probe         download + checksum-verify + structurally audit the
                          requested months into --output-dir
    --mode audit-local   re-run the structural audit against already
                          -downloaded files in --output-dir; no network

`--mode probe` reports `SOURCE_PROBE_PASSED/FAILED` -- network-confirmed
evidence. `--mode audit-local` reports the conceptually separate
`LOCAL_AUDIT_PASSED/FAILED` -- it never claims network reachability, only
that the locally retained bytes are checksum-verified and structurally
complete.

Process exit code: 0 for `SOURCE_PROBE_PASSED`/`LOCAL_AUDIT_PASSED`
(and always for `--mode inventory`, which only constructs URLs); non-zero
otherwise.

Examples:

    python -m scripts.research.core_btc_binance_v0_probe --mode inventory
    python -m scripts.research.core_btc_binance_v0_probe --mode probe \\
        --output-dir artifacts/research_data_probe
    python -m scripts.research.core_btc_binance_v0_probe --mode audit-local \\
        --output-dir artifacts/research_data_probe
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.research.core_btc_binance_v0_probe_lib import (
    ARCHIVE_CLASS,
    DATASET_ACCEPTANCE_NOTE,
    DEFAULT_PROBE_MONTHS,
    INTERVAL,
    MARKET_TYPE,
    MONTH_PASS_PREDICATE_VERSION,
    PROBE_TOOL_VERSION,
    PROVIDER,
    REPORT_KIND,
    REPORT_SCHEMA_VERSION,
    SYMBOL,
    CoreBtcBinanceV0ProbeError,
    archive_urls,
    audit_klines,
    decide_existing_zip_disposition,
    evaluate_checksum_verification,
    evaluate_local_audit_pass,
    evaluate_month_pass,
    expected_csv_member_name,
    local_checksum_filename,
    local_zip_filename,
    overall_probe_status,
    parse_checksum_text,
    parse_kline_csv,
    read_kline_csv_member,
    sha256_of_bytes,
    sha256_of_file,
    validate_year_month,
)

UTC = timezone.utc
DEFAULT_OUTPUT_DIR = Path("artifacts/research_data_probe")
DEFAULT_REPORT_NAME = "CORE_BTC_BINANCE_V0_probe_inventory.json"
DEFAULT_TIMEOUT_SECONDS = 60.0
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


# ---------------------------------------------------------------------------
# RT-08: atomic writes. One writer per output directory is assumed -- this
# is fail-closed research reproducibility, not production-grade distributed
# locking. Concurrent runs against the SAME --output-dir are not supported.
# ---------------------------------------------------------------------------
def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _write_if_absent_atomic(path: Path, text: str) -> None:
    """Never overwrite a file that already exists -- see RT-05: an existing
    checksum sidecar is part of a prior revision's identity just as much as
    its ZIP is, and must not be silently replaced just because a probe run
    happened to re-fetch the (possibly different) current remote text."""
    if path.exists():
        return
    _atomic_write_text(path, text)


def _detect_git_commit_sha() -> str:
    """Best-effort provenance only. Never allowed to crash or make test
    behavior environment-dependent -- callers that need determinism (all
    unit tests) pass an explicit `git_commit_sha` instead of calling this."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(_REPO_ROOT), capture_output=True,
            text=True, timeout=3, check=True)
        sha = result.stdout.strip()
        return sha if sha else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _empty_month_record(year_month: str) -> dict:
    zip_url, checksum_url = archive_urls(year_month)
    return {
        "year_month": year_month,
        "provider": PROVIDER,
        "market_type": MARKET_TYPE,
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "archive_class": ARCHIVE_CLASS,
        "source_url": zip_url,
        "checksum_url": checksum_url,
        "expected_zip_filename": local_zip_filename(year_month),
        "expected_csv_member_name": expected_csv_member_name(year_month),
        "attempted": False,
        "acquired_at_utc": None,
        "source_status": "NOT_REQUESTED",
        "checksum_http_status": None,
        "byte_size": None,
        "expected_sha256": None,
        "expected_sha256_status": "NOT_REQUESTED",
        "checksum_observed_filename": None,
        "local_sha256": None,
        "checksum_verification": "NOT_ATTEMPTED",
        "zip_member_names": None,
        "parser_status": "NOT_ATTEMPTED",
        "header_present": None,
        "expected_rows": None,
        "observed_rows": None,
        "observed_unique_open_times": None,
        "missing_bucket_count": None,
        "duplicate_count": None,
        "duplicate_open_times": None,
        "missing_open_time_ranges_ms": None,
        "rows_outside_month_bounds": None,
        "is_strictly_ordered_by_open_time": None,
        "malformed_row_count": None,
        "invariant_violation_count": None,
        "invariant_violations": None,
        "first_open_time_ms": None,
        "last_open_time_ms": None,
        "month_passed": False,
        "local_audit_passed": None,
    }


# ---------------------------------------------------------------------------
# mode: inventory
# ---------------------------------------------------------------------------
def run_inventory(months: list[str], git_commit_sha: str = "UNKNOWN") -> dict:
    records = [_empty_month_record(ym) for ym in months]
    return _build_report("inventory", records, git_commit_sha)


# ---------------------------------------------------------------------------
# mode: audit-local (no network)
# ---------------------------------------------------------------------------
def _audit_one_local_month(output_dir: Path, year_month: str) -> dict:
    record = _empty_month_record(year_month)
    record["attempted"] = True
    zip_path = output_dir / local_zip_filename(year_month)
    checksum_path = output_dir / local_checksum_filename(year_month)

    if not zip_path.exists():
        record["source_status"] = "NO_LOCAL_FILE"
        record["local_audit_passed"] = False
        return record

    record["byte_size"] = zip_path.stat().st_size
    record["local_sha256"] = sha256_of_file(zip_path)

    parsed_checksum = None
    if checksum_path.exists():
        try:
            parsed_checksum = parse_checksum_text(checksum_path.read_text(encoding="utf-8"))
            record["expected_sha256"] = parsed_checksum["sha256"]
            record["expected_sha256_status"] = "PRESENT"
            record["checksum_observed_filename"] = parsed_checksum["filename"]
        except CoreBtcBinanceV0ProbeError as exc:
            record["expected_sha256_status"] = f"MALFORMED: {exc}"
    else:
        record["expected_sha256_status"] = "MISSING_LOCAL_CHECKSUM_FILE"

    record["checksum_verification"] = evaluate_checksum_verification(
        record["local_sha256"], parsed_checksum, record["expected_zip_filename"])

    # RT-06: this is LOCAL evidence only -- never labeled as an HTTP status.
    record["source_status"] = "LOCAL_FILE_PRESENT"
    _fill_parse_and_audit(record, zip_path, year_month)
    record["local_audit_passed"] = evaluate_local_audit_pass(record)
    record["month_passed"] = False  # audit-local never confirms network reachability
    return record


def run_audit_local(output_dir: Path, months: list[str], git_commit_sha: str = "UNKNOWN") -> dict:
    records = [_audit_one_local_month(output_dir, ym) for ym in months]
    return _build_report("audit-local", records, git_commit_sha)


def _fill_parse_and_audit(record: dict, zip_path: Path, year_month: str) -> None:
    csv_text, member_names, parser_status = read_kline_csv_member(zip_path, year_month)
    record["zip_member_names"] = member_names
    record["parser_status"] = parser_status
    if parser_status != "OK" or csv_text is None:
        return
    rows, parse_meta = parse_kline_csv(csv_text)
    record["header_present"] = parse_meta["header_present"]
    audit = audit_klines(rows, year_month, parse_meta["malformed_row_count"])
    record.update(audit)


# ---------------------------------------------------------------------------
# mode: probe (network)
# ---------------------------------------------------------------------------
async def _fetch(session, url: str, timeout_seconds: float) -> tuple[Optional[bytes], str]:
    import aiohttp

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as resp:
            if resp.status == 200:
                return await resp.read(), "HTTP_200"
            return None, f"HTTP_{resp.status}"
    except aiohttp.ClientError as exc:
        return None, f"NETWORK_ERROR:{exc.__class__.__name__}"
    except asyncio.TimeoutError:
        return None, "NETWORK_ERROR:Timeout"


async def _probe_one_month(session, output_dir: Path, year_month: str, timeout_seconds: float) -> dict:
    record = _empty_month_record(year_month)
    record["attempted"] = True
    zip_path = output_dir / local_zip_filename(year_month)
    checksum_path = output_dir / local_checksum_filename(year_month)

    checksum_bytes, checksum_http_status = await _fetch(session, record["checksum_url"], timeout_seconds)
    record["checksum_http_status"] = checksum_http_status
    parsed_checksum = None
    checksum_text_decoded = None
    if checksum_bytes is not None:
        checksum_text_decoded = checksum_bytes.decode("utf-8", errors="replace")
        try:
            parsed_checksum = parse_checksum_text(checksum_text_decoded)
            record["expected_sha256"] = parsed_checksum["sha256"]
            record["expected_sha256_status"] = "PRESENT"
            record["checksum_observed_filename"] = parsed_checksum["filename"]
        except CoreBtcBinanceV0ProbeError as exc:
            record["expected_sha256_status"] = f"MALFORMED: {exc}"
    else:
        record["expected_sha256_status"] = f"MISSING: {checksum_http_status}"

    expected_sha256 = parsed_checksum["sha256"] if parsed_checksum else None
    existing_sha256 = sha256_of_file(zip_path) if zip_path.exists() else None
    disposition = decide_existing_zip_disposition(existing_sha256, expected_sha256)

    if disposition == "REVISION_CONFLICT":
        # RT-05: fail closed WITHOUT writing anything at all for this month
        # -- neither the existing ZIP nor its checksum sidecar may be
        # touched. The freshly observed remote checksum is recorded in the
        # report only; adopting it is a deliberate action outside this
        # probe's automatic behavior (move the old revision aside, or use a
        # different --output-dir).
        record["source_status"] = "REVISION_CONFLICT"
        record["local_sha256"] = existing_sha256
        record["checksum_verification"] = "MISMATCH"
        record["acquired_at_utc"] = _now_iso()
        return record

    # From here on we are NOT overwriting any existing revision -- it is
    # safe to persist the freshly retrieved checksum sidecar, but ONLY if
    # none is already on disk (idempotent; never touches an existing one).
    if checksum_text_decoded is not None:
        _write_if_absent_atomic(checksum_path, checksum_text_decoded)

    if disposition in ("REUSED_IDENTICAL", "REUSED_UNVERIFIED_NO_REFERENCE"):
        record["source_status"] = disposition
        record["local_sha256"] = existing_sha256
        record["byte_size"] = zip_path.stat().st_size
        record["acquired_at_utc"] = _now_iso()
    else:  # NEW: actually download
        zip_bytes, zip_http_status = await _fetch(session, record["source_url"], timeout_seconds)
        record["acquired_at_utc"] = _now_iso()
        if zip_bytes is None:
            record["source_status"] = zip_http_status
            return record
        _atomic_write_bytes(zip_path, zip_bytes)
        record["byte_size"] = len(zip_bytes)
        record["local_sha256"] = sha256_of_bytes(zip_bytes)
        record["source_status"] = "HTTP_200"

    record["checksum_verification"] = evaluate_checksum_verification(
        record["local_sha256"], parsed_checksum, record["expected_zip_filename"])

    _fill_parse_and_audit(record, zip_path, year_month)
    record["month_passed"] = evaluate_month_pass(record)
    return record


async def _run_probe_async(
    output_dir: Path, months: list[str], timeout_seconds: float, git_commit_sha: str = "UNKNOWN",
) -> dict:
    import aiohttp

    output_dir.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        records = [await _probe_one_month(session, output_dir, ym, timeout_seconds) for ym in months]
    return _build_report("probe", records, git_commit_sha)


def run_probe(
    output_dir: Path, months: list[str], timeout_seconds: float, git_commit_sha: str = "UNKNOWN",
) -> dict:
    return asyncio.run(_run_probe_async(output_dir, months, timeout_seconds, git_commit_sha))


# ---------------------------------------------------------------------------
# report assembly
# ---------------------------------------------------------------------------
def _build_report(mode: str, records: list[dict], git_commit_sha: str) -> dict:
    records_sorted = sorted(records, key=lambda r: r["year_month"])
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "probe_tool_version": PROBE_TOOL_VERSION,
        "month_pass_predicate_version": MONTH_PASS_PREDICATE_VERSION,
        "report_kind": REPORT_KIND,
        "generated_at_utc": _now_iso(),
        "provenance_git_commit_sha": git_commit_sha,
        "mode": mode,
        "dataset_id": "CORE_BTC_BINANCE_V0",
        "contract_path": "docs/CORE_BTC_BINANCE_V0_CONTRACT.md",
        "manifest_path": "docs/manifests/CORE_BTC_BINANCE_V0.yaml",
        "provider": PROVIDER,
        "market_type": MARKET_TYPE,
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "probe_months": [r["year_month"] for r in records_sorted],
        "months": records_sorted,
        "overall_status": overall_probe_status(records_sorted, mode),
        "dataset_acceptance_note": DATASET_ACCEPTANCE_NOTE,
    }


def _serialize(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_months(raw: list[str]) -> list[str]:
    for ym in raw:
        validate_year_month(ym)
    return list(raw)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", required=True, choices=["inventory", "probe", "audit-local"])
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                    help="directory for downloaded probe files and the report (probe/audit-local)")
    p.add_argument("--months", nargs="+", default=list(DEFAULT_PROBE_MONTHS),
                    help=f"probe months as YYYY-MM (default: {' '.join(DEFAULT_PROBE_MONTHS)})")
    p.add_argument("--report-path", type=Path, default=None,
                    help=f"override report output path (default: <output-dir>/{DEFAULT_REPORT_NAME})")
    p.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    p.add_argument("--provenance-git-commit-sha", type=str, default=None,
                    help="override the report's provenance git commit SHA; auto-detected via "
                         "'git rev-parse HEAD' when omitted, or 'UNKNOWN' if that fails")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    months = _parse_months(args.months)
    report_path = args.report_path or (args.output_dir / DEFAULT_REPORT_NAME)
    git_commit_sha = args.provenance_git_commit_sha or _detect_git_commit_sha()

    if args.mode == "inventory":
        report = run_inventory(months, git_commit_sha)
    elif args.mode == "probe":
        report = run_probe(args.output_dir, months, args.timeout_seconds, git_commit_sha)
    else:
        report = run_audit_local(args.output_dir, months, git_commit_sha)

    serialized = _serialize(report)
    if args.mode != "inventory":
        report_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(report_path, serialized)
        print(f"wrote {report_path}", file=sys.stderr)
    print(serialized, end="")
    print(f"overall_status={report['overall_status']} (NOT dataset acceptance)", file=sys.stderr)

    if args.mode == "inventory":
        return 0
    return 0 if report["overall_status"] in ("SOURCE_PROBE_PASSED", "LOCAL_AUDIT_PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
