"""Outcome-blind materializer for B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.

Downloads only the frozen Binance Vision joint-period objects, validates them
through the already-frozen contract, and binds a computed snapshot identity to
exact Git commit/tree blobs. It does not authorize B2-06 science, invent
funding publication latency, or open 2025/2026.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import yaml

from scripts.research.binance_um_oi_funding_v0_contract_lib import (
    AVAILABILITY_SEMANTICS_VERSION,
    CONTRACT_PATH,
    DATASET_ID,
    FROZEN_SOURCE,
    FUNDING_CSV_MEMBER_TEMPLATE,
    FUNDING_PUBLICATION_SEMANTICS_STATUS,
    JOINT_DEVELOPMENT_END_EXCLUSIVE,
    JOINT_DEVELOPMENT_START_INCLUSIVE,
    MANIFEST_PATH,
    NORMALIZATION_MODULE,
    OI_CSV_MEMBER_TEMPLATE,
    SNAPSHOT_AUTHORITY_KIND,
    OiFundingAuthorizationError,
    OiFundingCorruptError,
    OiFundingIdentityError,
    OiFundingLookaheadError,
    OiFundingMissingError,
    assert_funding_legally_consumable,
    assert_outcome_access_closed,
    bind_snapshot_to_tracked_authority,
    dumps_deterministic,
    expected_oi_period_starts,
    funding_object_name,
    funding_settlement_denominator,
    funding_urls,
    missing_oi_intervals,
    normalize_funding_rows,
    normalize_oi_rows,
    oi_object_name,
    oi_urls,
    reject_caller_asserted_funding_publication,
    sha256_hex,
    sha256_of_canonical_identity_payload,
    validate_archive_zip_members,
    verify_oi_funding_git_authority,
    verify_source_checksum,
)
from scripts.research.lib.research_harness import (
    CodeIdentityError,
    DatasetIdentityError,
    read_frozen_git_bytes,
)

UTC = timezone.utc
FetchFn = Callable[[str], tuple[bytes | None, int]]

MATERIALIZER_VERSION = "v1-binance-vision-oi-funding-sha256sum"
MATERIALIZER_MODULE = "scripts/research/binance_um_oi_funding_v0_materializer_lib.py"
MATERIALIZER_CLI_MODULE = "scripts/research/binance_um_oi_funding_v0_materializer.py"
MATERIALIZED_STATUS = "SNAPSHOT_MATERIALIZED_NOT_RESEARCH_AUTHORIZED"
DEFAULT_DATASET_ROOT = Path("artifacts/research_data") / DATASET_ID
EVIDENCE_GIT_DIR = Path("docs/research_data") / DATASET_ID
USER_AGENT = "signalbot-research/binance-um-oi-funding-v0-materializer"
SNAPSHOT_IDENTITY_VERSION = "v3-materialized-exact-git-object-authority"
LOCK_FILENAME = ".oi_funding_v0.lock"
CHECKSUM_SIDECAR_STATUS = "TRANSIENT_CORROBORATING_EVIDENCE_NOT_GIT_RETAINED"
DURABILITY_STATUS = "IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED"


class CachingFetch:
    """Memoize exact URL bytes. Unknown URLs are not invented."""

    def __init__(self, fetch: FetchFn) -> None:
        self._fetch = fetch
        self._cache: dict[str, tuple[bytes | None, int]] = {}

    def __call__(self, url: str) -> tuple[bytes | None, int]:
        if url not in self._cache:
            self._cache[url] = self._fetch(url)
        return self._cache[url]


class StrictPrefetchFetch:
    """Fail closed if the materializer requests an object that was not predeclared."""

    def __init__(self, cache: Mapping[str, tuple[bytes | None, int]]) -> None:
        self._cache = dict(cache)

    def __call__(self, url: str) -> tuple[bytes | None, int]:
        if url not in self._cache:
            raise OiFundingIdentityError(f"unexpected archive object URL: {url}")
        return self._cache[url]


@dataclass(frozen=True)
class RequestedArchiveObject:
    series: str
    period: str
    zip_name: str
    member_name: str
    zip_url: str
    checksum_url: str


def _joint_start_date() -> date:
    return datetime.fromisoformat(
        JOINT_DEVELOPMENT_START_INCLUSIVE.replace("Z", "+00:00")
    ).date()


def _joint_end_date_exclusive() -> date:
    return datetime.fromisoformat(
        JOINT_DEVELOPMENT_END_EXCLUSIVE.replace("Z", "+00:00")
    ).date()


def expected_joint_oi_days() -> list[str]:
    start = _joint_start_date()
    end = _joint_end_date_exclusive()
    if start != date(2020, 9, 1) or end != date(2025, 1, 1):
        raise OiFundingIdentityError("frozen joint OI period drifted")
    out: list[str] = []
    cursor = start
    while cursor < end:
        out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    if len(out) != 1583:
        raise OiFundingCorruptError(f"frozen OI day count drifted: {len(out)}")
    return out


def expected_joint_funding_months() -> list[str]:
    start = _joint_start_date()
    end_exclusive = _joint_end_date_exclusive()
    out: list[str] = []
    year, month = start.year, start.month
    while date(year, month, 1) < end_exclusive:
        out.append(f"{year:04d}-{month:02d}")
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    if out[0] != "2020-09" or out[-1] != "2024-12" or len(out) != 52:
        raise OiFundingCorruptError(
            f"frozen funding month count drifted: {out[:3]}..{out[-3:]}"
        )
    return out


def frozen_requested_objects() -> list[RequestedArchiveObject]:
    objects: list[RequestedArchiveObject] = []
    for month in expected_joint_funding_months():
        year_n, month_n = (int(part) for part in month.split("-"))
        zip_name = funding_object_name(month)
        zip_url, checksum_url = funding_urls(month)
        objects.append(
            RequestedArchiveObject(
                series="funding",
                period=month,
                zip_name=zip_name,
                member_name=FUNDING_CSV_MEMBER_TEMPLATE.format(
                    year=year_n, month=month_n
                ),
                zip_url=zip_url,
                checksum_url=checksum_url,
            )
        )
    for day in expected_joint_oi_days():
        year_n, month_n, day_n = (int(part) for part in day.split("-"))
        zip_name = oi_object_name(day)
        zip_url, checksum_url = oi_urls(day)
        objects.append(
            RequestedArchiveObject(
                series="oi",
                period=day,
                zip_name=zip_name,
                member_name=OI_CSV_MEMBER_TEMPLATE.format(
                    year=year_n, month=month_n, day=day_n
                ),
                zip_url=zip_url,
                checksum_url=checksum_url,
            )
        )
    return objects


def require_frozen_request_set(
    objects: Sequence[RequestedArchiveObject],
    *,
    allow_restricted_fixture: bool = False,
) -> list[RequestedArchiveObject]:
    requested = list(objects)
    expected = frozen_requested_objects()
    expected_names = {item.zip_name for item in expected}
    requested_names = [item.zip_name for item in requested]
    extra = [name for name in requested_names if name not in expected_names]
    if extra:
        raise OiFundingIdentityError(
            f"unexpected archive object outside frozen joint period: {extra[:5]}"
        )
    if requested == expected:
        return requested
    if not allow_restricted_fixture:
        raise OiFundingIdentityError(
            "requested archive set is not the frozen joint period"
        )
    if not requested:
        raise OiFundingIdentityError("restricted fixture requested zero archives")
    seen: set[str] = set()
    for item in requested:
        if item.zip_name in seen:
            raise OiFundingIdentityError(
                f"duplicate requested archive object: {item.zip_name}"
            )
        seen.add(item.zip_name)
        if item not in expected:
            raise OiFundingIdentityError(
                f"restricted fixture object is not a frozen identity: {item.zip_name}"
            )
    return requested


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing == data:
            return
        raise OiFundingCorruptError(
            f"refusing to overwrite differing existing file {path}"
        )
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    written = path.read_bytes()
    if written != data:
        raise OiFundingCorruptError(f"post-write verification failed for {path}")


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def urllib_fetch(url: str, timeout_seconds: float = 60.0) -> tuple[bytes | None, int]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.read(), int(response.status)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, 404
        raise OiFundingCorruptError(f"HTTP {exc.code} fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise OiFundingCorruptError(f"transport failure fetching {url}") from exc


def retrying_urllib_fetch(
    url: str,
    *,
    attempts: int = 4,
    timeout_seconds: float = 60.0,
) -> tuple[bytes | None, int]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return urllib_fetch(url, timeout_seconds=timeout_seconds)
        except OiFundingCorruptError as exc:
            last_error = exc
            if "HTTP 404" in str(exc):
                raise
            if attempt == attempts - 1:
                raise
            continue
    raise OiFundingCorruptError(f"transport failure fetching {url}") from last_error


@contextmanager
def dataset_lock(dataset_root: Path) -> Iterator[None]:
    dataset_root = Path(dataset_root)
    dataset_root.mkdir(parents=True, exist_ok=True)
    lock_path = dataset_root / LOCK_FILENAME
    handle = open(lock_path, "w", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OiFundingCorruptError(
                f"dataset root is locked by another writer: {dataset_root}"
            ) from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _row_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))


def _normalized_jsonl(rows: Sequence[Any]) -> bytes:
    lines = [_row_json(asdict(row)) for row in rows]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def _assert_funding_not_legally_consumable(row: Any) -> None:
    try:
        assert_funding_legally_consumable(row, row.source_event_time_ms)
    except (OiFundingLookaheadError, OiFundingAuthorizationError):
        return
    raise OiFundingAuthorizationError(
        "funding calc_time was treated as legal availability during materialization"
    )


def materialize_one_object(
    requested: RequestedArchiveObject,
    *,
    identity: Mapping[str, Any],
    fetch: FetchFn,
) -> dict[str, Any]:
    if requested.series not in {"oi", "funding"}:
        raise OiFundingIdentityError(f"unknown series {requested.series!r}")
    zip_bytes, zip_status = fetch(requested.zip_url)
    checksum_bytes, checksum_status = fetch(requested.checksum_url)
    record: dict[str, Any] = {
        "series": requested.series,
        "period": requested.period,
        "archive_object_name": requested.zip_name,
        "zip_url": requested.zip_url,
        "checksum_url": requested.checksum_url,
        "expected_member_name": requested.member_name,
        "retrieval_status": "FETCHED",
        "http_status_zip": zip_status,
        "http_status_checksum": checksum_status,
        "rejection_reason": None,
        "research_authorized": False,
        "outcome_access_authorized": False,
        "b2_06_evaluator_enabled": False,
        "funding_publication_semantics_status": FUNDING_PUBLICATION_SEMANTICS_STATUS,
    }
    if zip_bytes is None or checksum_bytes is None or zip_status != 200 or checksum_status != 200:
        record["retrieval_status"] = "MISSING"
        record["rejection_reason"] = "missing expected object"
        raise OiFundingMissingError(
            f"missing expected archive object {requested.zip_name}"
        )
    record["container_bytes"] = len(zip_bytes)
    record["container_sha256"] = sha256_hex(zip_bytes)
    try:
        checksum_text = checksum_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OiFundingCorruptError(
            f"checksum sidecar is not UTF-8 for {requested.zip_name}"
        ) from exc
    verify_source_checksum(
        zip_bytes=zip_bytes,
        checksum_text=checksum_text,
        expected_zip_filename=requested.zip_name,
    )
    record["checksum_verification"] = "VERIFIED"
    member_bytes = validate_archive_zip_members(
        zip_bytes, expected_member_name=requested.member_name
    )
    record["member_identity"] = requested.member_name
    record["archive_member_validation"] = "ACCEPTED"
    record["member_bytes"] = len(member_bytes)
    record["member_sha256"] = sha256_hex(member_bytes)
    try:
        csv_text = member_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OiFundingCorruptError(
            f"truncated or malformed CSV in {requested.zip_name}"
        ) from exc
    if requested.series == "funding":
        rows = normalize_funding_rows(
            csv_text,
            identity=identity,
            archive_object_name=requested.zip_name,
        )
        for row in rows:
            reject_caller_asserted_funding_publication(row)
            _assert_funding_not_legally_consumable(row)
            if row.legal_available_at_ms is not None:
                raise OiFundingAuthorizationError(
                    "funding calc_time must not be treated as legal_available_at"
                )
        denom = funding_settlement_denominator(rows, year_month=requested.period)
        record["parsed_row_count"] = len(csv_text.strip().splitlines()) - 1
        record["normalized_row_count"] = len(rows)
        record["min_source_timestamp_ms"] = (
            rows[0].source_event_time_ms if rows else None
        )
        record["max_source_timestamp_ms"] = (
            rows[-1].source_event_time_ms if rows else None
        )
        record["gap_count"] = denom["gap_count"]
        record["missing_native_periods"] = denom["missing_settlements"]
        record["present_valid_settlements"] = denom["present_valid_settlements"]
        record["expected_native_periods"] = len(denom["expected_settlements"])
        record["gap_completeness_result"] = "ENUMERATED_MISSING_NOT_FILLED"
        record["duplicate_handling"] = "ENTIRE_FROZEN_RAW_ROW"
        record["normalized_rows"] = rows
        if not rows:
            raise OiFundingCorruptError(
                f"funding archive {requested.zip_name} produced zero normalized rows"
            )
        if record["expected_native_periods"] is None:
            raise OiFundingCorruptError("unexplained missing native funding periods")
    else:
        rows = normalize_oi_rows(
            csv_text,
            identity=identity,
            archive_object_name=requested.zip_name,
        )
        missing = missing_oi_intervals(rows, day_yyyy_mm_dd=requested.period)
        collapsed = sum(1 for row in rows if row.identical_duplicate_collapsed)
        record["parsed_row_count"] = len(csv_text.strip().splitlines()) - 1
        record["normalized_row_count"] = len(rows)
        record["min_source_timestamp_ms"] = (
            rows[0].source_event_time_ms if rows else None
        )
        record["max_source_timestamp_ms"] = (
            rows[-1].source_event_time_ms if rows else None
        )
        record["gap_count"] = len(missing)
        record["missing_native_periods"] = missing
        record["expected_native_periods"] = len(
            expected_oi_period_starts(requested.period)
        )
        record["gap_completeness_result"] = "ENUMERATED_MISSING_NOT_FILLED"
        record["identical_duplicates_collapsed"] = collapsed
        record["duplicate_handling"] = "ENTIRE_FROZEN_RAW_ROW"
        record["normalized_rows"] = rows
        if not rows:
            raise OiFundingCorruptError(
                f"OI archive {requested.zip_name} produced zero normalized rows"
            )
        if record["expected_native_periods"] != 288:
            raise OiFundingCorruptError("unexplained missing native OI periods")
    return record


def build_materialized_snapshot_identity(
    *,
    git_authority: Any,
    materializer_source_sha256: str,
    materializer_cli_sha256: str | None,
    source_object_identities: Sequence[Mapping[str, Any]],
    normalized_objects: Sequence[Mapping[str, Any]],
    requested_intervals: Mapping[str, Any],
    row_counts: Mapping[str, int],
    first_last_timestamps: Mapping[str, Mapping[str, str]],
    gap_census: Mapping[str, Any],
) -> dict[str, Any]:
    if git_authority.manifest.get("research_authorized") is not False:
        raise OiFundingAuthorizationError("research_authorized must remain false")
    contract_sha = sha256_hex(
        read_frozen_git_bytes(git_authority.code_freeze, CONTRACT_PATH)
    )
    manifest_sha = sha256_hex(
        read_frozen_git_bytes(git_authority.code_freeze, git_authority.manifest_git_path)
    )
    payload = {
        "dataset_id": DATASET_ID,
        "contract_path": CONTRACT_PATH,
        "contract_sha256": contract_sha,
        "schema_version": "v1",
        "availability_semantics_version": AVAILABILITY_SEMANTICS_VERSION,
        "normalization_version": "v1",
        "retrieval_method_version": "binance-vision-official-archive-sha256sum-v1",
        "snapshot_identity_version": SNAPSHOT_IDENTITY_VERSION,
        "snapshot_authority": SNAPSHOT_AUTHORITY_KIND,
        "normalization_module": NORMALIZATION_MODULE,
        "normalization_source_sha256": git_authority.normalization_source_sha256,
        "materializer_module": MATERIALIZER_MODULE,
        "materializer_version": MATERIALIZER_VERSION,
        "materializer_source_sha256": materializer_source_sha256,
        "materializer_cli_module": MATERIALIZER_CLI_MODULE,
        "materializer_cli_sha256": materializer_cli_sha256,
        "manifest_git_path": git_authority.manifest_git_path,
        "manifest_blob_sha256": manifest_sha,
        "source_identity": dict(FROZEN_SOURCE),
        "requested_intervals": dict(requested_intervals),
        "source_object_identities": list(source_object_identities),
        "normalized_object_identities": list(normalized_objects),
        "row_counts": dict(row_counts),
        "first_last_timestamps": dict(first_last_timestamps),
        "gap_census": dict(gap_census),
        "provenance_git_commit_sha": git_authority.authority_commit_sha,
        "provenance_git_tree_sha": git_authority.authority_tree_sha,
        "funding_publication_semantics_status": FUNDING_PUBLICATION_SEMANTICS_STATUS,
        "funding_calc_time_is_legal_available_at": False,
        "oi_availability_rule": "period_end_bar_end_exclusive",
        "oi_decision_time_availability_proven": True,
        "funding_decision_time_availability_proven": False,
        "b2_06_inputs_legally_consumable": False,
        "research_authorized": False,
        "confirmatory_authorized": False,
        "outcome_access_authorized": False,
        "b2_06_evaluator_enabled": False,
    }
    snapshot_id = sha256_of_canonical_identity_payload(payload)
    return {"snapshot_id": snapshot_id, "identity_payload": payload}


def require_no_caller_hash_substitution(
    *,
    actual_sha256: str,
    claimed_sha256: str | None,
    label: str,
) -> None:
    if claimed_sha256 is None:
        return
    if claimed_sha256 != actual_sha256:
        raise OiFundingCorruptError(
            f"caller-forged {label} hash: {claimed_sha256} != {actual_sha256}"
        )


def bind_materialized_snapshot(
    *,
    git_authority: Any,
    snapshot: Mapping[str, Any],
    claimed_snapshot_id: str | None = None,
    claimed_manifest: Mapping[str, Any] | None = None,
    tracked_manifest: Mapping[str, Any] | None = None,
) -> str:
    if tracked_manifest is not None or claimed_manifest is not None:
        raise OiFundingAuthorizationError(
            "caller-supplied manifest mapping is not Git authority"
        )
    bound = bind_snapshot_to_tracked_authority(git_authority=git_authority)
    computed = snapshot.get("snapshot_id")
    if not isinstance(computed, str) or len(computed) != 64:
        raise OiFundingAuthorizationError("materialized snapshot_id missing")
    if claimed_snapshot_id not in (None, computed, "NOT_MATERIALIZED"):
        raise OiFundingAuthorizationError("snapshot-id tampering is forbidden")
    if bound not in {"NOT_MATERIALIZED", computed}:
        raise OiFundingAuthorizationError("Git-tracked snapshot_id mismatch")
    assert_outcome_access_closed(git_authority.manifest)
    assert_outcome_access_closed(snapshot.get("identity_payload") or {})
    if snapshot.get("identity_payload", {}).get("research_authorized") is not False:
        raise OiFundingAuthorizationError(
            "materialized snapshot cannot authorize research"
        )
    return computed


def write_snapshot_bundle(
    *,
    dataset_root: Path,
    snapshot: Mapping[str, Any],
    object_ledger: Sequence[Mapping[str, Any]],
    quality_report: Mapping[str, Any],
) -> dict[str, str]:
    dataset_root = Path(dataset_root)
    reports = dataset_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    snapshot_bytes = dumps_deterministic(dict(snapshot)).encode("utf-8")
    ledger_bytes = dumps_deterministic({"objects": list(object_ledger)}).encode("utf-8")
    quality_bytes = dumps_deterministic(dict(quality_report)).encode("utf-8")
    paths = {
        "snapshot_manifest": reports / "snapshot_manifest.json",
        "object_ledger": reports / "object_ledger.json",
        "quality_report": reports / "quality_report.json",
    }
    atomic_write_bytes(paths["snapshot_manifest"], snapshot_bytes)
    atomic_write_bytes(paths["object_ledger"], ledger_bytes)
    atomic_write_bytes(paths["quality_report"], quality_bytes)
    return {
        "snapshot_manifest_sha256": sha256_hex(snapshot_bytes),
        "object_ledger_sha256": sha256_hex(ledger_bytes),
        "quality_report_sha256": sha256_hex(quality_bytes),
        "snapshot_id": str(snapshot["snapshot_id"]),
    }


def _git_output(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            detail = exc.stderr.decode("utf-8", errors="replace").strip().splitlines()
            detail = detail[0] if detail else ""
        raise OiFundingAuthorizationError(
            "git command failed: "
            + " ".join(args)
            + (f" ({detail})" if detail else "")
        ) from exc
    return result.stdout.decode("utf-8").strip()


def _require_40_hex(value: str, label: str) -> str:
    text = value.strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise OiFundingAuthorizationError(f"{label} must be an exact 40-hex SHA")
    return text


def _require_64_hex(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise OiFundingCorruptError(f"missing {label}")
    text = value.strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise OiFundingCorruptError(f"{label} must be an exact 64-hex digest")
    if value != text:
        raise OiFundingCorruptError(f"{label} must be lowercase hex")
    return text


def read_commit_blob(repo_root: Path, commit_sha: str, git_path: str) -> bytes:
    """Read a blob from an exact commit without requiring HEAD to equal it."""
    commit = _require_40_hex(commit_sha, "commit_sha")
    if not git_path or git_path.startswith("/") or ".." in Path(git_path).parts:
        raise OiFundingAuthorizationError(f"invalid git path {git_path!r}")
    listing = subprocess.run(
        ["git", "-C", str(repo_root), "ls-tree", "-z", commit, "--", git_path],
        capture_output=True,
        check=False,
    )
    if listing.returncode != 0 or not listing.stdout.strip(b"\0"):
        raise OiFundingAuthorizationError(
            f"tracked Git path absent from {commit}: {git_path}"
        )
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "blob", f"{commit}:{git_path}"],
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise OiFundingAuthorizationError(
            f"unable to cat-file {commit}:{git_path}"
        ) from exc


def evidence_paths_for_snapshot(snapshot_id: str) -> dict[str, str]:
    prefix = _require_64_hex(snapshot_id, "snapshot_id")[:8]
    base = EVIDENCE_GIT_DIR.as_posix()
    return {
        "snapshot": f"{base}/SNAPSHOT_{prefix}.json",
        "object_ledger": f"{base}/OBJECT_LEDGER_{prefix}.json",
        "quality_report": f"{base}/QUALITY_REPORT_{prefix}.json",
        "readme": f"{base}/README.md",
    }


def render_evidence_readme(
    *,
    snapshot_id: str,
    snapshot_manifest_sha256: str,
    object_ledger_sha256: str,
    quality_report_sha256: str,
    provenance_git_commit_sha: str,
    provenance_git_tree_sha: str,
    expected_oi_objects: int,
    expected_funding_objects: int,
    accepted_oi_objects: int,
    accepted_funding_objects: int,
    rejected_oi_objects: int,
    rejected_funding_objects: int,
    raw_byte_total: int,
    normalized_byte_total: int,
) -> str:
    prefix = snapshot_id[:8]
    return (
        f"# {DATASET_ID} snapshot evidence\n\n"
        f"**Status:** `{MATERIALIZED_STATUS}`\n"
        f"**Snapshot ID:** `{snapshot_id}`\n"
        f"**Materializer commit:** `{provenance_git_commit_sha}`\n"
        f"**Materializer tree:** `{provenance_git_tree_sha}`\n\n"
        "These files are byte-identical copies of the runtime artifacts under the\n"
        f"gitignored dataset root `artifacts/research_data/{DATASET_ID}/`.\n\n"
        "| Archival file | Runtime source | SHA-256 |\n"
        "|---|---|---|\n"
        f"| `SNAPSHOT_{prefix}.json` | `reports/snapshot_manifest.json` | `{snapshot_manifest_sha256}` |\n"
        f"| `OBJECT_LEDGER_{prefix}.json` | `reports/object_ledger.json` | `{object_ledger_sha256}` |\n"
        f"| `QUALITY_REPORT_{prefix}.json` | `reports/quality_report.json` | `{quality_report_sha256}` |\n\n"
        "Joint period `[2020-09-01, 2025-01-01)`:\n\n"
        f"- OI objects expected/fetched/accepted/rejected = {expected_oi_objects} / {accepted_oi_objects} / {accepted_oi_objects} / {rejected_oi_objects}\n"
        f"- funding objects expected/fetched/accepted/rejected = {expected_funding_objects} / {accepted_funding_objects} / {accepted_funding_objects} / {rejected_funding_objects}\n"
        f"- raw container bytes = {raw_byte_total}\n"
        f"- normalized JSONL bytes = {normalized_byte_total}\n\n"
        "Authorization remains closed:\n\n"
        "- `research_authorized = false`\n"
        "- `outcome_access_authorized = false`\n"
        "- `b2_06_evaluator_enabled = false`\n"
        "- funding publication = `FUNDING_PUBLICATION_LATENCY_UNPROVEN`\n\n"
        "## Durability\n\n"
        "- Raw ZIP bytes are gitignored and not currently retained in Git.\n"
        "- Normalized JSONL bytes are gitignored and not currently retained in Git.\n"
        "- `.CHECKSUM` sidecars are transient corroborating evidence only; they are "
        "not Git-retained.\n"
        "- This snapshot proves exact historical existence/identity at materialization "
        "time.\n"
        "- Exact future recovery depends on upstream Binance Vision bytes remaining "
        "available and unchanged unless separate durable retention is added.\n"
        "- This repository does not currently claim local recoverability of the raw "
        "or normalized bytes.\n"
        f"- Durability status: `{DURABILITY_STATUS}`.\n"
        f"- Checksum sidecar status: `{CHECKSUM_SIDECAR_STATUS}`.\n\n"
        "Canonical repository manifest: "
        f"`{MANIFEST_PATH}`.\n"
    )


def copy_identity_evidence_to_git(
    *,
    repo_root: Path,
    dataset_root: Path,
    snapshot_id: str,
) -> dict[str, Path]:
    src_reports = Path(dataset_root) / "reports"
    dest = Path(repo_root) / EVIDENCE_GIT_DIR
    dest.mkdir(parents=True, exist_ok=True)
    paths = evidence_paths_for_snapshot(snapshot_id)
    mapping = {
        src_reports / "snapshot_manifest.json": Path(repo_root) / paths["snapshot"],
        src_reports / "object_ledger.json": Path(repo_root) / paths["object_ledger"],
        src_reports / "quality_report.json": Path(repo_root) / paths["quality_report"],
    }
    written: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    for src, dst in mapping.items():
        data = src.read_bytes()
        atomic_write_bytes(dst, data)
        written[dst.name] = dst
        hashes[dst.name] = sha256_hex(data)
    quality = json.loads(
        (src_reports / "quality_report.json").read_text(encoding="utf-8")
    )
    snapshot = json.loads(
        (src_reports / "snapshot_manifest.json").read_text(encoding="utf-8")
    )
    payload = snapshot.get("identity_payload") or {}
    readme = Path(repo_root) / paths["readme"]
    readme_text = render_evidence_readme(
        snapshot_id=snapshot_id,
        snapshot_manifest_sha256=hashes[Path(paths["snapshot"]).name],
        object_ledger_sha256=hashes[Path(paths["object_ledger"]).name],
        quality_report_sha256=hashes[Path(paths["quality_report"]).name],
        provenance_git_commit_sha=str(payload.get("provenance_git_commit_sha") or ""),
        provenance_git_tree_sha=str(payload.get("provenance_git_tree_sha") or ""),
        expected_oi_objects=int(quality["expected_oi_objects"]),
        expected_funding_objects=int(quality["expected_funding_objects"]),
        accepted_oi_objects=int(quality["accepted_oi_objects"]),
        accepted_funding_objects=int(quality["accepted_funding_objects"]),
        rejected_oi_objects=int(quality["rejected_oi_objects"]),
        rejected_funding_objects=int(quality["rejected_funding_objects"]),
        raw_byte_total=int(quality["raw_byte_total"]),
        normalized_byte_total=int(quality["normalized_byte_total"]),
    )
    atomic_write_text(readme, readme_text)
    written[readme.name] = readme
    return written


def _require_worktree_matches_head(
    repo_root: Path, git_path: str, head_sha: str
) -> bytes:
    blob = read_commit_blob(repo_root, head_sha, git_path)
    worktree = Path(repo_root) / git_path
    if not worktree.is_file():
        raise OiFundingCorruptError(f"missing worktree evidence file {git_path}")
    worktree_bytes = worktree.read_bytes()
    if worktree_bytes != blob:
        raise OiFundingCorruptError(
            f"worktree bytes differ from tracked Git blob for {git_path}"
        )
    return blob


def verify_committed_oi_funding_evidence(
    *,
    repo_root: Path,
    claimed_hashes: Mapping[str, str] | None = None,
    claimed_manifest: Mapping[str, Any] | None = None,
    tracked_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify the committed evidence bundle without downloading.

    Authority is the current HEAD Git blobs plus the historical provenance
    commit recorded in the tracked manifest. Callers cannot supply hashes or
    mappings. HEAD does not need to equal the pre-materialization commit.
    """
    if claimed_manifest is not None or tracked_manifest is not None:
        raise OiFundingAuthorizationError(
            "caller-supplied manifest mapping is not Git authority"
        )
    repo_root = Path(repo_root).resolve()
    head_sha = _require_40_hex(_git_output(repo_root, "rev-parse", "HEAD"), "HEAD")
    head_tree = _require_40_hex(
        _git_output(repo_root, "rev-parse", "HEAD^{tree}"), "HEAD tree"
    )
    yaml_bytes = _require_worktree_matches_head(repo_root, MANIFEST_PATH, head_sha)
    try:
        manifest = yaml.safe_load(yaml_bytes.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise OiFundingAuthorizationError("tracked manifest is not valid UTF-8 YAML") from exc
    if not isinstance(manifest, dict):
        raise OiFundingAuthorizationError("tracked manifest must be a mapping")
    if manifest.get("dataset_id") != DATASET_ID:
        raise OiFundingIdentityError("tracked manifest dataset_id mismatch")
    if manifest.get("research_authorized") is not False:
        raise OiFundingAuthorizationError("research_authorized must remain false")
    if manifest.get("outcome_access_authorized") not in (False, None):
        raise OiFundingAuthorizationError("outcome access is not authorized")
    if manifest.get("b2_06_evaluator_enabled") not in (False, None):
        raise OiFundingAuthorizationError("scientific evaluator is not authorized")
    snapshot_id = _require_64_hex(manifest.get("snapshot_id"), "snapshot_id")
    expected_snapshot_hash = _require_64_hex(
        manifest.get("snapshot_manifest_sha256"), "snapshot_manifest_sha256"
    )
    expected_ledger_hash = _require_64_hex(
        manifest.get("object_ledger_sha256"), "object_ledger_sha256"
    )
    expected_quality_hash = _require_64_hex(
        manifest.get("quality_report_sha256"), "quality_report_sha256"
    )
    paths = evidence_paths_for_snapshot(snapshot_id)
    snapshot_bytes = _require_worktree_matches_head(repo_root, paths["snapshot"], head_sha)
    ledger_bytes = _require_worktree_matches_head(
        repo_root, paths["object_ledger"], head_sha
    )
    quality_bytes = _require_worktree_matches_head(
        repo_root, paths["quality_report"], head_sha
    )
    readme_bytes = _require_worktree_matches_head(repo_root, paths["readme"], head_sha)
    actual = {
        "snapshot_manifest_sha256": sha256_hex(snapshot_bytes),
        "object_ledger_sha256": sha256_hex(ledger_bytes),
        "quality_report_sha256": sha256_hex(quality_bytes),
    }
    claimed_hashes = dict(claimed_hashes or {})
    for label, actual_digest in actual.items():
        require_no_caller_hash_substitution(
            actual_sha256=actual_digest,
            claimed_sha256=claimed_hashes.get(label),
            label=label,
        )
    if actual["snapshot_manifest_sha256"] != expected_snapshot_hash:
        raise OiFundingCorruptError("snapshot manifest SHA256 does not match tracked manifest")
    if actual["object_ledger_sha256"] != expected_ledger_hash:
        raise OiFundingCorruptError("object ledger SHA256 does not match tracked manifest")
    if actual["quality_report_sha256"] != expected_quality_hash:
        raise OiFundingCorruptError("quality report SHA256 does not match tracked manifest")
    try:
        snapshot = json.loads(snapshot_bytes.decode("utf-8"))
        ledger = json.loads(ledger_bytes.decode("utf-8"))
        quality = json.loads(quality_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OiFundingCorruptError("committed evidence JSON is malformed") from exc
    if snapshot.get("snapshot_id") != snapshot_id:
        raise OiFundingCorruptError("snapshot file snapshot_id mismatch")
    payload = snapshot.get("identity_payload")
    if not isinstance(payload, dict):
        raise OiFundingCorruptError("snapshot identity_payload missing")
    recomputed = sha256_of_canonical_identity_payload(payload)
    if recomputed != snapshot_id:
        raise OiFundingCorruptError("snapshot_id does not hash to identity_payload")
    if quality.get("snapshot_id") != snapshot_id:
        raise OiFundingCorruptError("quality report snapshot_id mismatch")
    if quality.get("snapshot_manifest_sha256") != actual["snapshot_manifest_sha256"]:
        raise OiFundingCorruptError("quality report snapshot_manifest_sha256 mismatch")
    if quality.get("research_authorized") is not False:
        raise OiFundingAuthorizationError("quality report cannot authorize research")
    if quality.get("funding_publication_semantics_status") != FUNDING_PUBLICATION_SEMANTICS_STATUS:
        raise OiFundingAuthorizationError("funding publication status drifted")
    objects = ledger.get("objects")
    if not isinstance(objects, list):
        raise OiFundingCorruptError("object ledger objects list missing")
    oi_n = sum(1 for item in objects if item.get("series") == "oi")
    funding_n = sum(1 for item in objects if item.get("series") == "funding")
    joint = manifest.get("joint_period") or {}
    expected_oi = int(joint.get("expected_oi_objects", quality.get("expected_oi_objects")))
    expected_funding = int(
        joint.get("expected_funding_objects", quality.get("expected_funding_objects"))
    )
    if oi_n != expected_oi or funding_n != expected_funding:
        raise OiFundingCorruptError("object ledger headline counts drifted")
    if int(quality.get("accepted_oi_objects", -1)) != oi_n:
        raise OiFundingCorruptError("quality OI count does not match ledger")
    if int(quality.get("accepted_funding_objects", -1)) != funding_n:
        raise OiFundingCorruptError("quality funding count does not match ledger")
    if len(payload.get("source_object_identities") or []) != oi_n + funding_n:
        raise OiFundingCorruptError("snapshot source_object_identities count drifted")
    provenance_commit = _require_40_hex(
        str(manifest.get("provenance_git_commit_sha") or payload.get("provenance_git_commit_sha") or ""),
        "provenance_git_commit_sha",
    )
    provenance_tree = _require_40_hex(
        str(manifest.get("provenance_git_tree_sha") or payload.get("provenance_git_tree_sha") or ""),
        "provenance_git_tree_sha",
    )
    actual_tree = _require_40_hex(
        _git_output(
            repo_root,
            "rev-parse",
            "--verify",
            f"{provenance_commit}^{{tree}}",
        ),
        "provenance tree",
    )
    if actual_tree != provenance_tree:
        raise OiFundingAuthorizationError("provenance tree does not match tracked Git authority")
    if provenance_commit != payload.get("provenance_git_commit_sha"):
        raise OiFundingAuthorizationError("snapshot provenance commit drifted")
    contract_sha = sha256_hex(read_commit_blob(repo_root, provenance_commit, CONTRACT_PATH))
    norm_sha = sha256_hex(read_commit_blob(repo_root, provenance_commit, NORMALIZATION_MODULE))
    mat_sha = sha256_hex(read_commit_blob(repo_root, provenance_commit, MATERIALIZER_MODULE))
    cli_sha = sha256_hex(read_commit_blob(repo_root, provenance_commit, MATERIALIZER_CLI_MODULE))
    if contract_sha != payload.get("contract_sha256"):
        raise OiFundingAuthorizationError("contract blob does not match snapshot Git authority")
    if norm_sha != payload.get("normalization_source_sha256"):
        raise OiFundingAuthorizationError(
            "normalization blob does not match snapshot Git authority"
        )
    if mat_sha != payload.get("materializer_source_sha256"):
        raise OiFundingAuthorizationError(
            "materializer blob does not match snapshot Git authority"
        )
    if cli_sha != payload.get("materializer_cli_sha256"):
        raise OiFundingAuthorizationError(
            "materializer CLI blob does not match snapshot Git authority"
        )
    generated_readme = render_evidence_readme(
        snapshot_id=snapshot_id,
        snapshot_manifest_sha256=actual["snapshot_manifest_sha256"],
        object_ledger_sha256=actual["object_ledger_sha256"],
        quality_report_sha256=actual["quality_report_sha256"],
        provenance_git_commit_sha=provenance_commit,
        provenance_git_tree_sha=provenance_tree,
        expected_oi_objects=expected_oi,
        expected_funding_objects=expected_funding,
        accepted_oi_objects=oi_n,
        accepted_funding_objects=funding_n,
        rejected_oi_objects=int(quality.get("rejected_oi_objects", 0)),
        rejected_funding_objects=int(quality.get("rejected_funding_objects", 0)),
        raw_byte_total=int(quality["raw_byte_total"]),
        normalized_byte_total=int(quality["normalized_byte_total"]),
    )
    if readme_bytes.decode("utf-8") != generated_readme:
        raise OiFundingCorruptError("evidence README is not the deterministic generated text")
    assert_outcome_access_closed(manifest)
    assert_outcome_access_closed(quality)
    return {
        "snapshot_id": snapshot_id,
        "head_sha": head_sha,
        "head_tree": head_tree,
        "provenance_git_commit_sha": provenance_commit,
        "provenance_git_tree_sha": provenance_tree,
        **actual,
        "accepted_oi_objects": oi_n,
        "accepted_funding_objects": funding_n,
        "research_authorized": False,
        "outcome_access_authorized": False,
        "b2_06_evaluator_enabled": False,
        "funding_publication_semantics_status": FUNDING_PUBLICATION_SEMANTICS_STATUS,
        "checksum_sidecar_status": CHECKSUM_SIDECAR_STATUS,
        "durability_status": DURABILITY_STATUS,
        "network_required": False,
    }


def strip_runtime_rows(record: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out.pop("normalized_rows", None)
    return out


def assemble_normalized_artifacts(
    *,
    dataset_root: Path,
    object_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    oi_rows: list[Any] = []
    funding_rows: list[Any] = []
    for record in object_records:
        rows = record.get("normalized_rows") or []
        if record["series"] == "oi":
            oi_rows.extend(rows)
        else:
            funding_rows.extend(rows)
    canonical = Path(dataset_root) / "canonical"
    oi_bytes = _normalized_jsonl(oi_rows)
    funding_bytes = _normalized_jsonl(funding_rows)
    oi_path = canonical / "oi.jsonl"
    funding_path = canonical / "funding.jsonl"
    atomic_write_bytes(oi_path, oi_bytes)
    atomic_write_bytes(funding_path, funding_bytes)
    if oi_path.read_bytes() != oi_bytes or funding_path.read_bytes() != funding_bytes:
        raise OiFundingCorruptError("normalized artifact post-write verification failed")
    return {
        "normalized_objects": [
            {
                "path": "canonical/oi.jsonl",
                "sha256": sha256_hex(oi_bytes),
                "size_bytes": len(oi_bytes),
                "row_count": len(oi_rows),
            },
            {
                "path": "canonical/funding.jsonl",
                "sha256": sha256_hex(funding_bytes),
                "size_bytes": len(funding_bytes),
                "row_count": len(funding_rows),
            },
        ],
        "oi_row_count": len(oi_rows),
        "funding_row_count": len(funding_rows),
        "oi_bytes": len(oi_bytes),
        "funding_bytes": len(funding_bytes),
    }


def verify_written_source_bytes(
    *,
    dataset_root: Path,
    record: Mapping[str, Any],
) -> None:
    raw_dir = Path(dataset_root) / "raw" / str(record["series"])
    zip_path = raw_dir / str(record["archive_object_name"])
    checksum_path = raw_dir / f"{record['archive_object_name']}.CHECKSUM"
    zip_bytes = zip_path.read_bytes()
    if sha256_hex(zip_bytes) != record["container_sha256"]:
        raise OiFundingCorruptError(
            f"mutated source container bytes for {record['archive_object_name']}"
        )
    if len(zip_bytes) != record["container_bytes"]:
        raise OiFundingCorruptError(
            f"source container size drifted for {record['archive_object_name']}"
        )
    if not checksum_path.exists():
        raise OiFundingCorruptError(
            f"missing checksum sidecar for {record['archive_object_name']}"
        )


def run_materialization(
    *,
    repo_root: Path,
    dataset_root: Path,
    fetch: FetchFn,
    authority_commit_sha: str,
    authority_tree_sha: str,
    requested_objects: Sequence[RequestedArchiveObject] | None = None,
    allow_restricted_fixture: bool = False,
    claimed_hashes: Mapping[str, str] | None = None,
    claimed_manifest: Mapping[str, Any] | None = None,
    copy_git_evidence: bool = True,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    dataset_root = Path(dataset_root)
    with dataset_lock(dataset_root):
        return _run_materialization_locked(
            repo_root=repo_root,
            dataset_root=dataset_root,
            fetch=fetch,
            authority_commit_sha=authority_commit_sha,
            authority_tree_sha=authority_tree_sha,
            requested_objects=requested_objects,
            allow_restricted_fixture=allow_restricted_fixture,
            claimed_hashes=claimed_hashes,
            claimed_manifest=claimed_manifest,
            copy_git_evidence=copy_git_evidence,
        )


def _run_materialization_locked(
    *,
    repo_root: Path,
    dataset_root: Path,
    fetch: FetchFn,
    authority_commit_sha: str,
    authority_tree_sha: str,
    requested_objects: Sequence[RequestedArchiveObject] | None,
    allow_restricted_fixture: bool,
    claimed_hashes: Mapping[str, str] | None,
    claimed_manifest: Mapping[str, Any] | None,
    copy_git_evidence: bool,
) -> dict[str, Any]:
    git_authority = verify_oi_funding_git_authority(
        repo_root=repo_root,
        authority_commit_sha=authority_commit_sha,
        authority_tree_sha=authority_tree_sha,
    )
    materializer_bytes = read_frozen_git_bytes(
        git_authority.code_freeze, MATERIALIZER_MODULE
    )
    materializer_sha = sha256_hex(materializer_bytes)
    try:
        cli_bytes = read_frozen_git_bytes(
            git_authority.code_freeze, MATERIALIZER_CLI_MODULE
        )
        cli_sha = sha256_hex(cli_bytes)
    except (CodeIdentityError, DatasetIdentityError) as exc:
        if allow_restricted_fixture:
            cli_sha = None
        else:
            raise OiFundingAuthorizationError(
                "materializer CLI blob is required in the frozen Git tree"
            ) from exc
    if requested_objects is None:
        if allow_restricted_fixture:
            raise OiFundingIdentityError(
                "restricted fixture flag cannot be used with the production object set"
            )
        objects = frozen_requested_objects()
        require_frozen_request_set(objects, allow_restricted_fixture=False)
    else:
        objects = require_frozen_request_set(
            requested_objects,
            allow_restricted_fixture=allow_restricted_fixture,
        )
    claimed_hashes = dict(claimed_hashes or {})
    fetch = CachingFetch(fetch)
    require_no_caller_hash_substitution(
        actual_sha256=git_authority.normalization_source_sha256,
        claimed_sha256=claimed_hashes.get("normalization"),
        label="normalization",
    )
    require_no_caller_hash_substitution(
        actual_sha256=materializer_sha,
        claimed_sha256=claimed_hashes.get("materializer"),
        label="materializer",
    )
    identity = dict(FROZEN_SOURCE)
    object_records: list[dict[str, Any]] = []
    for requested in objects:
        record = materialize_one_object(requested, identity=identity, fetch=fetch)
        raw_dir = dataset_root / "raw" / requested.series
        zip_path = raw_dir / requested.zip_name
        checksum_path = raw_dir / f"{requested.zip_name}.CHECKSUM"
        zip_bytes, _ = fetch(requested.zip_url)
        checksum_bytes, _ = fetch(requested.checksum_url)
        if zip_bytes is None or checksum_bytes is None:
            raise OiFundingMissingError(
                f"object disappeared during write {requested.zip_name}"
            )
        require_no_caller_hash_substitution(
            actual_sha256=sha256_hex(zip_bytes),
            claimed_sha256=claimed_hashes.get(requested.zip_name),
            label=requested.zip_name,
        )
        atomic_write_bytes(zip_path, zip_bytes)
        atomic_write_text(checksum_path, checksum_bytes.decode("utf-8"))
        object_records.append(record)
        verify_written_source_bytes(dataset_root=dataset_root, record=record)
    normalized = assemble_normalized_artifacts(
        dataset_root=dataset_root, object_records=object_records
    )
    require_no_caller_hash_substitution(
        actual_sha256=normalized["normalized_objects"][0]["sha256"],
        claimed_sha256=claimed_hashes.get("normalized_oi"),
        label="normalized_oi",
    )
    require_no_caller_hash_substitution(
        actual_sha256=normalized["normalized_objects"][1]["sha256"],
        claimed_sha256=claimed_hashes.get("normalized_funding"),
        label="normalized_funding",
    )
    ledger = [strip_runtime_rows(record) for record in object_records]
    oi_records = [r for r in ledger if r["series"] == "oi"]
    funding_records = [r for r in ledger if r["series"] == "funding"]
    source_identities = [
        {
            "series": r["series"],
            "archive_object_name": r["archive_object_name"],
            "zip_url": r["zip_url"],
            "checksum_url": r["checksum_url"],
            "period": r["period"],
            "container_sha256": r["container_sha256"],
            "container_bytes": r["container_bytes"],
            "member_identity": r["member_identity"],
            "archive_member_validation": r["archive_member_validation"],
            "member_sha256": r["member_sha256"],
            "member_bytes": r["member_bytes"],
            "checksum_verification": r["checksum_verification"],
            "parsed_row_count": r["parsed_row_count"],
            "normalized_row_count": r["normalized_row_count"],
            "min_source_timestamp_ms": r["min_source_timestamp_ms"],
            "max_source_timestamp_ms": r["max_source_timestamp_ms"],
            "duplicate_handling": r["duplicate_handling"],
            "gap_completeness_result": r["gap_completeness_result"],
            "gap_count": r["gap_count"],
        }
        for r in ledger
    ]
    first_last = {
        "oi": {
            "first": str(oi_records[0]["min_source_timestamp_ms"]) if oi_records else "",
            "last": str(oi_records[-1]["max_source_timestamp_ms"]) if oi_records else "",
        },
        "funding": {
            "first": str(funding_records[0]["min_source_timestamp_ms"])
            if funding_records
            else "",
            "last": str(funding_records[-1]["max_source_timestamp_ms"])
            if funding_records
            else "",
        },
    }
    gap_census = {
        "oi_objects_with_gaps": sum(1 for r in oi_records if r["gap_count"]),
        "oi_missing_native_buckets": int(sum(r["gap_count"] for r in oi_records)),
        "funding_objects_with_gaps": sum(1 for r in funding_records if r["gap_count"]),
        "funding_missing_settlements": int(sum(r["gap_count"] for r in funding_records)),
        "missing_native_periods_are": "MISSING_NOT_CORRUPT",
        "unexplained_missing_native_periods": False,
    }
    snapshot = build_materialized_snapshot_identity(
        git_authority=git_authority,
        materializer_source_sha256=materializer_sha,
        materializer_cli_sha256=cli_sha,
        source_object_identities=source_identities,
        normalized_objects=normalized["normalized_objects"],
        requested_intervals={
            "oi_days": [o.period for o in objects if o.series == "oi"],
            "funding_months": [o.period for o in objects if o.series == "funding"],
            "start_inclusive": JOINT_DEVELOPMENT_START_INCLUSIVE,
            "end_exclusive": JOINT_DEVELOPMENT_END_EXCLUSIVE,
        },
        row_counts={
            "oi": normalized["oi_row_count"],
            "funding": normalized["funding_row_count"],
        },
        first_last_timestamps=first_last,
        gap_census=gap_census,
    )
    bound_id = bind_materialized_snapshot(
        git_authority=git_authority,
        snapshot=snapshot,
        claimed_snapshot_id=claimed_hashes.get("snapshot_id"),
        claimed_manifest=claimed_manifest,
    )
    if bound_id != snapshot["snapshot_id"]:
        raise OiFundingAuthorizationError("bound snapshot_id drifted")
    retrieval_time = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    quality = {
        "dataset_id": DATASET_ID,
        "status": MATERIALIZED_STATUS,
        "retrieval_time_utc": retrieval_time,
        "expected_oi_objects": sum(1 for o in objects if o.series == "oi"),
        "expected_funding_objects": sum(1 for o in objects if o.series == "funding"),
        "fetched_oi_objects": len(oi_records),
        "fetched_funding_objects": len(funding_records),
        "accepted_oi_objects": len(oi_records),
        "accepted_funding_objects": len(funding_records),
        "rejected_oi_objects": 0,
        "rejected_funding_objects": 0,
        "raw_byte_total": int(sum(r["container_bytes"] for r in ledger)),
        "normalized_byte_total": int(
            normalized["oi_bytes"] + normalized["funding_bytes"]
        ),
        "gap_census": gap_census,
        "research_authorized": False,
        "outcome_access_authorized": False,
        "b2_06_evaluator_enabled": False,
        "funding_publication_semantics_status": FUNDING_PUBLICATION_SEMANTICS_STATUS,
        "funding_decision_time_availability_proven": False,
        "oi_decision_time_availability_proven": True,
        "b2_06_inputs_legally_consumable": False,
        "snapshot_id": snapshot["snapshot_id"],
        "provenance_git_commit_sha": git_authority.authority_commit_sha,
        "provenance_git_tree_sha": git_authority.authority_tree_sha,
    }
    hashes = write_snapshot_bundle(
        dataset_root=dataset_root,
        snapshot=snapshot,
        object_ledger=ledger,
        quality_report=quality,
    )
    quality["snapshot_manifest_sha256"] = hashes["snapshot_manifest_sha256"]
    quality_path = dataset_root / "reports" / "quality_report.json"
    if quality_path.exists() and quality_path.read_bytes() != dumps_deterministic(
        quality
    ).encode("utf-8"):
        # First write omitted the file hash; replace only the quality report
        # after recomputing snapshot_manifest_sha256.
        quality_path.unlink()
    atomic_write_bytes(quality_path, dumps_deterministic(quality).encode("utf-8"))
    hashes["quality_report_sha256"] = sha256_hex(quality_path.read_bytes())
    hashes["snapshot_manifest_sha256"] = sha256_hex(
        (dataset_root / "reports" / "snapshot_manifest.json").read_bytes()
    )
    if copy_git_evidence:
        copy_identity_evidence_to_git(
            repo_root=repo_root,
            dataset_root=dataset_root,
            snapshot_id=snapshot["snapshot_id"],
        )
    assert_outcome_access_closed(quality)
    return {
        "snapshot": snapshot,
        "quality": quality,
        "hashes": hashes,
        "git_authority": git_authority,
        "object_count": len(ledger),
        "ledger": ledger,
    }
