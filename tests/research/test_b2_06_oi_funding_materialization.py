"""Fail-closed tests for B2-06 OI/funding snapshot materialization.

Fixtures are local. No test inspects B2-06 predictive outcomes, opens 2025/2026,
or treats calc_time as legal availability.
"""
from __future__ import annotations

import inspect
import io
import json
import subprocess
import urllib.request
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from scripts.research.binance_um_oi_funding_v0_contract_lib import (
    CONTRACT_PATH,
    FROZEN_SOURCE,
    FUNDING_HEADER,
    FUNDING_PERIOD_MS,
    FUNDING_PUBLICATION_PROVEN_STATUS,
    MANIFEST_PATH,
    NORMALIZATION_MODULE,
    OI_HEADER,
    OI_PERIOD_MS,
    OiFundingAuthorizationError,
    OiFundingCorruptError,
    OiFundingIdentityError,
    OiFundingMissingError,
    reject_caller_asserted_funding_publication,
    sha256_hex,
    sha256_of_canonical_identity_payload,
)
from scripts.research.binance_um_oi_funding_v0_materializer_lib import (
    EVIDENCE_GIT_DIR,
    MATERIALIZER_CLI_MODULE,
    MATERIALIZER_MODULE,
    RequestedArchiveObject,
    StrictPrefetchFetch,
    bind_materialized_snapshot,
    copy_identity_evidence_to_git,
    expected_joint_funding_months,
    expected_joint_oi_days,
    frozen_requested_objects,
    funding_object_name,
    funding_urls,
    materialize_one_object,
    oi_object_name,
    oi_urls,
    read_commit_blob,
    render_evidence_readme,
    require_frozen_request_set,
    require_no_caller_hash_substitution,
    run_materialization,
    verify_committed_oi_funding_evidence,
    verify_oi_funding_git_authority,
    verify_written_source_bytes,
)

UTC = timezone.utc
REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / CONTRACT_PATH
MANIFEST = REPO / MANIFEST_PATH
NORM = REPO / NORMALIZATION_MODULE
MAT_LIB = REPO / MATERIALIZER_MODULE
MAT_CLI = REPO / MATERIALIZER_CLI_MODULE

DAY0 = 1598918400000  # 2020-09-01T00:00:00Z
OI_DAY = "2020-09-01"
FUNDING_MONTH = "2020-09"
OI_ZIP = "BTCUSDT-metrics-2020-09-01.zip"
FUNDING_ZIP = "BTCUSDT-fundingRate-2020-09.zip"
OI_MEMBER = "BTCUSDT-metrics-2020-09-01.csv"
FUNDING_MEMBER = "BTCUSDT-fundingRate-2020-09.csv"


def _dt(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")


def _oi_csv(rows: list[tuple[str, str, str]]) -> str:
    lines = [",".join(OI_HEADER)]
    for create_time, symbol, oi in rows:
        lines.append(
            ",".join(
                [create_time, symbol, oi, "100.0", "1.0", "1.0", "1.0", "1.0"]
            )
        )
    return "\n".join(lines) + "\n"


def _funding_csv(rows: list[tuple[int, str, str]]) -> str:
    lines = [",".join(FUNDING_HEADER)]
    for calc, hours, rate in rows:
        lines.append(f"{calc},{hours},{rate}")
    return "\n".join(lines) + "\n"


def _one_oi_day_csv(*, skip: set[int] | None = None, value: str = "39000.0") -> str:
    skip = skip or set()
    rows = []
    for i in range(288):
        start = DAY0 + i * OI_PERIOD_MS
        if start in skip:
            continue
        rows.append((_dt(start), "BTCUSDT", value if i == 0 else f"{39000 + i}.0"))
    return _oi_csv(rows)


def _zip_member(member: str, payload: str | bytes) -> bytes:
    buf = io.BytesIO()
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member, data)
    return buf.getvalue()


def _checksum(zip_name: str, zip_bytes: bytes) -> bytes:
    return f"{sha256_hex(zip_bytes)}  {zip_name}\n".encode("utf-8")


def _valid_oi_zip() -> bytes:
    return _zip_member(OI_MEMBER, _one_oi_day_csv())


def _valid_funding_zip() -> bytes:
    rows = [
        (DAY0, "8", "0.0001"),
        (DAY0 + FUNDING_PERIOD_MS, "8", "0.0002"),
        (DAY0 + 2 * FUNDING_PERIOD_MS, "8", "0.0003"),
    ]
    return _zip_member(FUNDING_MEMBER, _funding_csv(rows))


def _oi_object() -> RequestedArchiveObject:
    zip_url, checksum_url = oi_urls(OI_DAY)
    return RequestedArchiveObject(
        series="oi",
        period=OI_DAY,
        zip_name=OI_ZIP,
        member_name=OI_MEMBER,
        zip_url=zip_url,
        checksum_url=checksum_url,
    )


def _funding_object() -> RequestedArchiveObject:
    zip_url, checksum_url = funding_urls(FUNDING_MONTH)
    return RequestedArchiveObject(
        series="funding",
        period=FUNDING_MONTH,
        zip_name=FUNDING_ZIP,
        member_name=FUNDING_MEMBER,
        zip_url=zip_url,
        checksum_url=checksum_url,
    )


def _store() -> dict[str, tuple[bytes | None, int]]:
    oi_zip = _valid_oi_zip()
    funding_zip = _valid_funding_zip()
    oi = _oi_object()
    funding = _funding_object()
    return {
        oi.zip_url: (oi_zip, 200),
        oi.checksum_url: (_checksum(OI_ZIP, oi_zip), 200),
        funding.zip_url: (funding_zip, 200),
        funding.checksum_url: (_checksum(FUNDING_ZIP, funding_zip), 200),
    }


def _fetch_from(store: dict[str, tuple[bytes | None, int]]):
    def fetch(url: str) -> tuple[bytes | None, int]:
        if url not in store:
            raise OiFundingIdentityError(f"unexpected archive object URL: {url}")
        return store[url]

    return fetch


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_commit(root: Path, message: str) -> str:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=B2-06 Materializer",
            "-c",
            "user.email=b206mat@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-m",
            message,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return _git(root, "rev-parse", "HEAD")


def _fixture_manifest_bytes() -> bytes:
    """Git fixtures must remain unmaterialized so a 1-object run can bind."""
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    data["status"] = "CONTRACT_FROZEN_NOT_MATERIALIZED"
    data["current_state"] = "CONTRACT_FROZEN_NOT_MATERIALIZED"
    data["snapshot_id"] = "NOT_MATERIALIZED"
    data["unit_verdict"] = (
        "DATA_CONTRACT_FROZEN_AWAITING_MATERIALIZATION_AND_FUNDING_AVAILABILITY_AUTHORITY"
    )
    data["research_authorized"] = False
    data["confirmatory_authorized"] = False
    data["outcome_access_authorized"] = False
    data["b2_06_evaluator_enabled"] = False
    data.pop("snapshot_manifest_sha256", None)
    data.pop("object_ledger_sha256", None)
    data.pop("quality_report_sha256", None)
    data.pop("provenance_git_commit_sha", None)
    data.pop("provenance_git_tree_sha", None)
    data.pop("materialized_at_utc", None)
    return yaml.safe_dump(data, sort_keys=False).encode("utf-8")


def _write_rel(root: Path, rel: str, data: bytes) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _init_materializer_repo(root: Path) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    _write_rel(root, MANIFEST_PATH, _fixture_manifest_bytes())
    _write_rel(root, CONTRACT_PATH, CONTRACT.read_bytes())
    _write_rel(root, NORMALIZATION_MODULE, NORM.read_bytes())
    _write_rel(root, MATERIALIZER_MODULE, MAT_LIB.read_bytes())
    _write_rel(root, MATERIALIZER_CLI_MODULE, MAT_CLI.read_bytes())
    _git(root, "add", "-A")
    sha = _git_commit(root, "authority")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    return {"sha": sha, "tree": tree}


def _run(tmp_path: Path, fetch, **kwargs):
    repo = tmp_path / "repo"
    ids = kwargs.pop("ids", None) or _init_materializer_repo(repo)
    dataset = kwargs.pop("dataset", tmp_path / "dataset")
    return run_materialization(
        repo_root=repo,
        dataset_root=dataset,
        fetch=fetch,
        authority_commit_sha=ids["sha"],
        authority_tree_sha=ids["tree"],
        requested_objects=kwargs.pop("requested_objects", [_funding_object(), _oi_object()]),
        allow_restricted_fixture=kwargs.pop("allow_restricted_fixture", True),
        **kwargs,
    )


def test_frozen_joint_coverage_is_exact():
    days = expected_joint_oi_days()
    months = expected_joint_funding_months()
    assert days[0] == "2020-09-01"
    assert days[-1] == "2024-12-31"
    assert len(days) == 1583
    assert months[0] == "2020-09"
    assert months[-1] == "2024-12"
    assert len(months) == 52
    objects = frozen_requested_objects()
    assert len(objects) == 1635
    require_frozen_request_set(objects)


def test_extra_archive_outside_frozen_period_is_rejected():
    extra = RequestedArchiveObject(
        series="oi",
        period="2025-01-01",
        zip_name="BTCUSDT-metrics-2025-01-01.zip",
        member_name="BTCUSDT-metrics-2025-01-01.csv",
        zip_url="https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2025-01-01.zip",
        checksum_url="https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2025-01-01.zip.CHECKSUM",
    )
    with pytest.raises(OiFundingIdentityError, match="unexpected archive object"):
        require_frozen_request_set([_oi_object(), extra], allow_restricted_fixture=True)


def test_restricted_list_without_fixture_flag_is_rejected():
    with pytest.raises(OiFundingIdentityError, match="not the frozen joint period"):
        require_frozen_request_set([_oi_object()], allow_restricted_fixture=False)


def test_successful_restricted_fixture_materializes_and_stays_unauthorized(tmp_path: Path):
    result = _run(tmp_path, _fetch_from(_store()))
    quality = result["quality"]
    snapshot = result["snapshot"]
    assert quality["accepted_oi_objects"] == 1
    assert quality["accepted_funding_objects"] == 1
    assert quality["rejected_oi_objects"] == 0
    assert quality["rejected_funding_objects"] == 0
    assert quality["research_authorized"] is False
    assert quality["outcome_access_authorized"] is False
    assert quality["b2_06_evaluator_enabled"] is False
    assert quality["b2_06_inputs_legally_consumable"] is False
    assert quality["funding_decision_time_availability_proven"] is False
    payload = snapshot["identity_payload"]
    assert payload["funding_calc_time_is_legal_available_at"] is False
    assert payload["research_authorized"] is False
    funding_rows = [
        obj for obj in result["ledger"] if obj["series"] == "funding"
    ]
    assert funding_rows[0]["gap_completeness_result"] == "ENUMERATED_MISSING_NOT_FILLED"
    assert funding_rows[0]["gap_count"] > 0


def test_missing_archive_fails_closed(tmp_path: Path):
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (None, 404)
    with pytest.raises(OiFundingMissingError, match="missing expected archive"):
        _run(tmp_path, _fetch_from(store))


def test_extra_zip_member_fails_closed(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(OI_MEMBER, _one_oi_day_csv())
        zf.writestr("readme.txt", "extra")
    oi_zip = buf.getvalue()
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="extra ZIP members|exactly one CSV"):
        _run(tmp_path, _fetch_from(store))


def test_corrupt_zip_fails_closed(tmp_path: Path):
    store = _store()
    oi = _oi_object()
    bad = b"not-a-zip"
    store[oi.zip_url] = (bad, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, bad), 200)
    with pytest.raises(OiFundingCorruptError, match="unsupported compression"):
        _run(tmp_path, _fetch_from(store))


def test_traversal_member_fails_closed(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../" + OI_MEMBER, _one_oi_day_csv())
    oi_zip = buf.getvalue()
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="traversal|unexpected ZIP member"):
        _run(tmp_path, _fetch_from(store))


def test_duplicate_member_fails_closed(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(OI_MEMBER, _one_oi_day_csv())
        zf.writestr(OI_MEMBER, _one_oi_day_csv())
    oi_zip = buf.getvalue()
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="duplicate ZIP member"):
        _run(tmp_path, _fetch_from(store))


def test_wrong_header_fails_closed(tmp_path: Path):
    csv_text = "foo,bar\n1,2\n"
    oi_zip = _zip_member(OI_MEMBER, csv_text)
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="schema mismatch"):
        _run(tmp_path, _fetch_from(store))


def test_wrong_archive_day_row_fails_closed(tmp_path: Path):
    previous = _dt(DAY0 - OI_PERIOD_MS)
    csv_text = _oi_csv([(previous, "BTCUSDT", "1.0")])
    oi_zip = _zip_member(OI_MEMBER, csv_text)
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="outside requested"):
        _run(tmp_path, _fetch_from(store))


def test_malformed_timestamp_fails_closed(tmp_path: Path):
    csv_text = _oi_csv([("not-a-timestamp", "BTCUSDT", "1.0")])
    oi_zip = _zip_member(OI_MEMBER, csv_text)
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="malformed timestamp"):
        _run(tmp_path, _fetch_from(store))


def test_impossible_date_object_is_corrupt():
    with pytest.raises(OiFundingCorruptError):
        oi_object_name("2023-02-29")
    with pytest.raises(OiFundingCorruptError):
        oi_object_name("0000-01-01")


def test_nan_inf_fails_closed(tmp_path: Path):
    csv_text = _one_oi_day_csv()
    csv_text = csv_text.replace("39000.0", "NaN", 1)
    oi_zip = _zip_member(OI_MEMBER, csv_text)
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="non-finite"):
        _run(tmp_path, _fetch_from(store))


def test_conflicting_duplicate_authoritative_values_fail(tmp_path: Path):
    csv_text = _oi_csv(
        [
            (_dt(DAY0), "BTCUSDT", "10.0"),
            (_dt(DAY0), "BTCUSDT", "11.0"),
        ]
    )
    oi_zip = _zip_member(OI_MEMBER, csv_text)
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="conflicting duplicate"):
        _run(tmp_path, _fetch_from(store))


def test_gaps_are_enumerated_not_filled(tmp_path: Path):
    skip = {DAY0 + 3 * OI_PERIOD_MS}
    oi_zip = _zip_member(OI_MEMBER, _one_oi_day_csv(skip=skip))
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    result = _run(tmp_path, _fetch_from(store))
    oi_rec = next(r for r in result["ledger"] if r["series"] == "oi")
    assert oi_rec["gap_count"] == 1
    assert skip.pop() in oi_rec["missing_native_periods"]
    assert oi_rec["gap_completeness_result"] == "ENUMERATED_MISSING_NOT_FILLED"


def test_wrong_source_identity_symbol_fails(tmp_path: Path):
    csv_text = _one_oi_day_csv().replace("BTCUSDT", "ETHUSDT")
    oi_zip = _zip_member(OI_MEMBER, csv_text)
    store = _store()
    oi = _oi_object()
    store[oi.zip_url] = (oi_zip, 200)
    store[oi.checksum_url] = (_checksum(OI_ZIP, oi_zip), 200)
    with pytest.raises(OiFundingIdentityError, match="symbol"):
        _run(tmp_path, _fetch_from(store))


def test_mutated_source_bytes_fail_post_write_check(tmp_path: Path):
    result = _run(tmp_path, _fetch_from(_store()))
    dataset = tmp_path / "dataset"
    oi_rec = next(r for r in result["ledger"] if r["series"] == "oi")
    zip_path = dataset / "raw" / "oi" / OI_ZIP
    zip_path.write_bytes(zip_path.read_bytes() + b"x")
    with pytest.raises(OiFundingCorruptError, match="mutated source container"):
        verify_written_source_bytes(dataset_root=dataset, record=oi_rec)


def test_mutated_normalized_bytes_change_identity(tmp_path: Path):
    result = _run(tmp_path, _fetch_from(_store()))
    dataset = tmp_path / "dataset"
    path = dataset / "canonical" / "oi.jsonl"
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    assert sha256_hex(path.read_bytes()) != result["snapshot"]["identity_payload"][
        "normalized_object_identities"
    ][0]["sha256"]


def test_reordered_or_incomplete_identity_payload_changes_snapshot_id(tmp_path: Path):
    result = _run(tmp_path, _fetch_from(_store()))
    payload = dict(result["snapshot"]["identity_payload"])
    original = result["snapshot"]["snapshot_id"]
    reordered = dict(payload)
    reordered["source_object_identities"] = list(
        reversed(list(payload["source_object_identities"]))
    )
    assert sha256_of_canonical_identity_payload(reordered) != original
    incomplete = dict(payload)
    incomplete.pop("provenance_git_commit_sha")
    assert sha256_of_canonical_identity_payload(incomplete) != original


def test_caller_forged_hashes_fail(tmp_path: Path):
    with pytest.raises(OiFundingCorruptError, match="caller-forged normalization"):
        _run(
            tmp_path,
            _fetch_from(_store()),
            claimed_hashes={"normalization": "0" * 64},
        )


def test_caller_forged_manifest_fails(tmp_path: Path):
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        _run(
            tmp_path,
            _fetch_from(_store()),
            claimed_manifest={"dataset_id": "forged"},
        )


def test_stale_git_authority_fails(tmp_path: Path):
    repo = tmp_path / "repo"
    ids = _init_materializer_repo(repo)
    with pytest.raises(OiFundingAuthorizationError, match="HEAD mismatch"):
        run_materialization(
            repo_root=repo,
            dataset_root=tmp_path / "dataset",
            fetch=_fetch_from(_store()),
            authority_commit_sha="0" * 40,
            authority_tree_sha=ids["tree"],
            requested_objects=[_funding_object(), _oi_object()],
            allow_restricted_fixture=True,
        )


def test_dirty_skip_worktree_assume_unchanged_fail(tmp_path: Path):
    repo = tmp_path / "repo"
    ids = _init_materializer_repo(repo)
    (repo / MANIFEST_PATH).write_text(
        (repo / MANIFEST_PATH).read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    with pytest.raises(OiFundingAuthorizationError, match="not clean"):
        run_materialization(
            repo_root=repo,
            dataset_root=tmp_path / "d1",
            fetch=_fetch_from(_store()),
            authority_commit_sha=ids["sha"],
            authority_tree_sha=ids["tree"],
            requested_objects=[_funding_object(), _oi_object()],
            allow_restricted_fixture=True,
        )
    repo2 = tmp_path / "repo2"
    ids2 = _init_materializer_repo(repo2)
    _git(repo2, "update-index", "--skip-worktree", MANIFEST_PATH)
    (repo2 / MANIFEST_PATH).write_text(
        (repo2 / MANIFEST_PATH).read_text(encoding="utf-8").replace(
            "research_authorized: false", "research_authorized: true"
        ),
        encoding="utf-8",
    )
    with pytest.raises(OiFundingAuthorizationError, match="skip-worktree"):
        run_materialization(
            repo_root=repo2,
            dataset_root=tmp_path / "d2",
            fetch=_fetch_from(_store()),
            authority_commit_sha=ids2["sha"],
            authority_tree_sha=ids2["tree"],
            requested_objects=[_funding_object(), _oi_object()],
            allow_restricted_fixture=True,
        )
    repo3 = tmp_path / "repo3"
    ids3 = _init_materializer_repo(repo3)
    _git(repo3, "update-index", "--assume-unchanged", MANIFEST_PATH)
    (repo3 / MANIFEST_PATH).write_text(
        (repo3 / MANIFEST_PATH).read_text(encoding="utf-8").replace(
            "research_authorized: false", "research_authorized: true"
        ),
        encoding="utf-8",
    )
    with pytest.raises(OiFundingAuthorizationError, match="assume-unchanged"):
        run_materialization(
            repo_root=repo3,
            dataset_root=tmp_path / "d3",
            fetch=_fetch_from(_store()),
            authority_commit_sha=ids3["sha"],
            authority_tree_sha=ids3["tree"],
            requested_objects=[_funding_object(), _oi_object()],
            allow_restricted_fixture=True,
        )


def test_snapshot_id_tampering_fails(tmp_path: Path):
    with pytest.raises(OiFundingAuthorizationError, match="snapshot-id tampering"):
        _run(
            tmp_path,
            _fetch_from(_store()),
            claimed_hashes={"snapshot_id": "a" * 64},
        )


def test_funding_calc_time_is_not_legal_availability(tmp_path: Path):
    result = _run(tmp_path, _fetch_from(_store()))
    payload = result["snapshot"]["identity_payload"]
    assert payload["funding_calc_time_is_legal_available_at"] is False
    assert payload["funding_decision_time_availability_proven"] is False
    funding_zip = _valid_funding_zip()
    record = materialize_one_object(
        _funding_object(),
        identity=dict(FROZEN_SOURCE),
        fetch=_fetch_from(
            {
                _funding_object().zip_url: (funding_zip, 200),
                _funding_object().checksum_url: (_checksum(FUNDING_ZIP, funding_zip), 200),
            }
        ),
    )
    for row in record["normalized_rows"]:
        assert row.legal_available_at_ms is None
        with pytest.raises(OiFundingAuthorizationError, match="caller cannot"):
            reject_caller_asserted_funding_publication(
                replace(row, legal_available_at_ms=row.source_event_time_ms)
            )


def test_caller_created_funding_row_cannot_self_attest(tmp_path: Path):
    result = _run(tmp_path, _fetch_from(_store()))
    funding_zip = _valid_funding_zip()
    record = materialize_one_object(
        _funding_object(),
        identity=dict(FROZEN_SOURCE),
        fetch=_fetch_from(
            {
                _funding_object().zip_url: (funding_zip, 200),
                _funding_object().checksum_url: (_checksum(FUNDING_ZIP, funding_zip), 200),
            }
        ),
    )
    row = record["normalized_rows"][0]
    forged = replace(
        row,
        publication_semantics_status=FUNDING_PUBLICATION_PROVEN_STATUS,
        legal_available_at_ms=row.source_event_time_ms,
    )
    with pytest.raises(OiFundingAuthorizationError, match="caller cannot"):
        reject_caller_asserted_funding_publication(forged)
    assert result["quality"]["b2_06_inputs_legally_consumable"] is False


def test_strict_prefetch_rejects_unexpected_url():
    fetch = StrictPrefetchFetch({"https://example.invalid/a": (b"x", 200)})
    with pytest.raises(OiFundingIdentityError, match="unexpected archive object URL"):
        fetch("https://data.binance.vision/not-requested.zip")


def test_cli_has_no_period_override():
    source = MAT_CLI.read_text(encoding="utf-8")
    assert "--allow-acquire" in source
    assert "--verify-only" in source
    assert "--start" not in source
    assert "--end" not in source
    assert "--period" not in source
    assert "period override is forbidden" in source


def test_bind_rejects_caller_snapshot_mapping(tmp_path: Path):
    repo = tmp_path / "repo"
    ids = _init_materializer_repo(repo)
    authority = verify_oi_funding_git_authority(
        repo_root=repo,
        authority_commit_sha=ids["sha"],
        authority_tree_sha=ids["tree"],
    )
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        bind_materialized_snapshot(
            git_authority=authority,
            snapshot={"snapshot_id": "a" * 64, "identity_payload": {"research_authorized": False}},
            tracked_manifest={"snapshot_id": "a" * 64},
        )


def test_require_no_caller_hash_substitution():
    require_no_caller_hash_substitution(
        actual_sha256="a" * 64, claimed_sha256=None, label="x"
    )
    require_no_caller_hash_substitution(
        actual_sha256="a" * 64, claimed_sha256="a" * 64, label="x"
    )
    with pytest.raises(OiFundingCorruptError, match="caller-forged"):
        require_no_caller_hash_substitution(
            actual_sha256="a" * 64, claimed_sha256="b" * 64, label="x"
        )


def test_wrong_funding_month_row_fails(tmp_path: Path):
    # 2020-08-01 00:00:00Z is outside September.
    csv_text = _funding_csv([(1596240000000, "8", "0.0001")])
    funding_zip = _zip_member(FUNDING_MEMBER, csv_text)
    store = _store()
    funding = _funding_object()
    store[funding.zip_url] = (funding_zip, 200)
    store[funding.checksum_url] = (_checksum(FUNDING_ZIP, funding_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="outside requested"):
        _run(tmp_path, _fetch_from(store))


def test_inf_funding_rate_fails(tmp_path: Path):
    csv_text = _funding_csv([(DAY0, "8", "Infinity")])
    funding_zip = _zip_member(FUNDING_MEMBER, csv_text)
    store = _store()
    funding = _funding_object()
    store[funding.zip_url] = (funding_zip, 200)
    store[funding.checksum_url] = (_checksum(FUNDING_ZIP, funding_zip), 200)
    with pytest.raises(OiFundingCorruptError, match="non-finite"):
        _run(tmp_path, _fetch_from(store))


def _clone_head(tmp_path: Path) -> Path:
    dest = tmp_path / "clone"
    # --no-local still copies from the current repo without network; --local
    # hardlinks fail in this environment when packfiles cannot be linked.
    subprocess.run(
        ["git", "clone", "--no-local", "--", str(REPO), str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    return dest


def _tracked_evidence_paths() -> dict[str, Path]:
    snapshot_id = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["snapshot_id"]
    prefix = snapshot_id[:8]
    base = REPO / EVIDENCE_GIT_DIR
    return {
        "snapshot_manifest_sha256": base / f"SNAPSHOT_{prefix}.json",
        "object_ledger_sha256": base / f"OBJECT_LEDGER_{prefix}.json",
        "quality_report_sha256": base / f"QUALITY_REPORT_{prefix}.json",
        "readme": base / "README.md",
    }


def _mutate_json(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["_redteam_mutation"] = True
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_committed_evidence_hashes_match_tracked_manifest():
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    paths = _tracked_evidence_paths()
    for label in (
        "snapshot_manifest_sha256",
        "object_ledger_sha256",
        "quality_report_sha256",
    ):
        actual = sha256_hex(paths[label].read_bytes())
        assert actual == manifest[label], label


def test_verify_committed_evidence_without_network(monkeypatch):
    source = inspect.getsource(verify_committed_oi_funding_evidence)
    assert "urlopen" not in source
    assert "urllib_fetch" not in source
    assert "retrying_urllib_fetch" not in source

    def boom(*_args, **_kwargs):
        raise AssertionError("network must not be used in verify-only")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    result = verify_committed_oi_funding_evidence(repo_root=REPO)
    assert result["network_required"] is False
    assert result["snapshot_id"] == (
        "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"
    )
    assert result["research_authorized"] is False
    assert result["outcome_access_authorized"] is False
    assert result["b2_06_evaluator_enabled"] is False
    assert result["funding_publication_semantics_status"] == (
        "FUNDING_PUBLICATION_LATENCY_UNPROVEN"
    )


def test_mutate_object_ledger_fails_verification(tmp_path: Path):
    clone = _clone_head(tmp_path)
    path = clone / EVIDENCE_GIT_DIR / "OBJECT_LEDGER_5a9d036b.json"
    _mutate_json(path)
    _git(clone, "add", "-A")
    _git_commit(clone, "mutate object ledger")
    with pytest.raises(OiFundingCorruptError, match="object ledger SHA256"):
        verify_committed_oi_funding_evidence(repo_root=clone)


def test_mutate_quality_report_fails_verification(tmp_path: Path):
    clone = _clone_head(tmp_path)
    path = clone / EVIDENCE_GIT_DIR / "QUALITY_REPORT_5a9d036b.json"
    _mutate_json(path)
    _git(clone, "add", "-A")
    _git_commit(clone, "mutate quality report")
    with pytest.raises(OiFundingCorruptError, match="quality report SHA256"):
        verify_committed_oi_funding_evidence(repo_root=clone)


def test_mutate_snapshot_manifest_fails_verification(tmp_path: Path):
    clone = _clone_head(tmp_path)
    path = clone / EVIDENCE_GIT_DIR / "SNAPSHOT_5a9d036b.json"
    _mutate_json(path)
    _git(clone, "add", "-A")
    _git_commit(clone, "mutate snapshot manifest")
    with pytest.raises(OiFundingCorruptError, match="snapshot manifest SHA256"):
        verify_committed_oi_funding_evidence(repo_root=clone)


def test_manifest_hash_forgery_fails():
    with pytest.raises(OiFundingCorruptError, match="caller-forged"):
        verify_committed_oi_funding_evidence(
            repo_root=REPO,
            claimed_hashes={"object_ledger_sha256": "0" * 64},
        )


def test_stale_evidence_manifest_fails(tmp_path: Path):
    clone = _clone_head(tmp_path)
    manifest_path = clone / MANIFEST_PATH
    text = manifest_path.read_text(encoding="utf-8")
    stale = text.replace(
        "521d42a471cc5fec74d808e8a4a3ea0078c87342b801df5dbf3836b4b69b4296",
        "a" * 64,
        1,
    )
    assert stale != text
    manifest_path.write_text(stale, encoding="utf-8")
    _git(clone, "add", "-A")
    _git_commit(clone, "stale evidence manifest")
    with pytest.raises(OiFundingCorruptError, match="object ledger SHA256"):
        verify_committed_oi_funding_evidence(repo_root=clone)


def test_verification_requires_exact_tracked_git_authority():
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        verify_committed_oi_funding_evidence(
            repo_root=REPO,
            claimed_manifest={"snapshot_id": "a" * 64},
        )
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        verify_committed_oi_funding_evidence(
            repo_root=REPO,
            tracked_manifest={"snapshot_id": "a" * 64},
        )
    with pytest.raises(OiFundingAuthorizationError, match="must be an exact 40-hex SHA"):
        read_commit_blob(REPO, "not-a-commit", MANIFEST_PATH)
    with pytest.raises(OiFundingAuthorizationError, match="tracked Git path absent"):
        read_commit_blob(REPO, "0" * 40, MANIFEST_PATH)


def test_readme_generation_is_idempotent(tmp_path: Path):
    result = _run(tmp_path, _fetch_from(_store()))
    repo = tmp_path / "repo"
    dataset = tmp_path / "dataset"
    snapshot_id = result["snapshot"]["snapshot_id"]
    copy_identity_evidence_to_git(
        repo_root=repo, dataset_root=dataset, snapshot_id=snapshot_id
    )
    copy_identity_evidence_to_git(
        repo_root=repo, dataset_root=dataset, snapshot_id=snapshot_id
    )
    payload = result["snapshot"]["identity_payload"]
    quality = result["quality"]
    hashes = result["hashes"]
    expected = render_evidence_readme(
        snapshot_id=snapshot_id,
        snapshot_manifest_sha256=hashes["snapshot_manifest_sha256"],
        object_ledger_sha256=hashes["object_ledger_sha256"],
        quality_report_sha256=hashes["quality_report_sha256"],
        provenance_git_commit_sha=payload["provenance_git_commit_sha"],
        provenance_git_tree_sha=payload["provenance_git_tree_sha"],
        expected_oi_objects=quality["expected_oi_objects"],
        expected_funding_objects=quality["expected_funding_objects"],
        accepted_oi_objects=quality["accepted_oi_objects"],
        accepted_funding_objects=quality["accepted_funding_objects"],
        rejected_oi_objects=quality["rejected_oi_objects"],
        rejected_funding_objects=quality["rejected_funding_objects"],
        raw_byte_total=quality["raw_byte_total"],
        normalized_byte_total=quality["normalized_byte_total"],
    )
    readme = (repo / EVIDENCE_GIT_DIR / "README.md").read_text(encoding="utf-8")
    assert readme == expected
    committed = _tracked_evidence_paths()["readme"].read_text(encoding="utf-8")
    live_manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    live_quality = json.loads(
        _tracked_evidence_paths()["quality_report_sha256"].read_text(encoding="utf-8")
    )
    live_expected = render_evidence_readme(
        snapshot_id=live_manifest["snapshot_id"],
        snapshot_manifest_sha256=live_manifest["snapshot_manifest_sha256"],
        object_ledger_sha256=live_manifest["object_ledger_sha256"],
        quality_report_sha256=live_manifest["quality_report_sha256"],
        provenance_git_commit_sha=live_manifest["provenance_git_commit_sha"],
        provenance_git_tree_sha=live_manifest["provenance_git_tree_sha"],
        expected_oi_objects=live_quality["expected_oi_objects"],
        expected_funding_objects=live_quality["expected_funding_objects"],
        accepted_oi_objects=live_quality["accepted_oi_objects"],
        accepted_funding_objects=live_quality["accepted_funding_objects"],
        rejected_oi_objects=live_quality["rejected_oi_objects"],
        rejected_funding_objects=live_quality["rejected_funding_objects"],
        raw_byte_total=live_quality["raw_byte_total"],
        normalized_byte_total=live_quality["normalized_byte_total"],
    )
    assert committed == live_expected


def test_verify_only_cli_does_not_prefetch(monkeypatch):
    from scripts.research.binance_um_oi_funding_v0_materializer import main

    def boom(*_args, **_kwargs):
        raise AssertionError("verify-only must not prefetch or download")

    monkeypatch.setattr(
        "scripts.research.binance_um_oi_funding_v0_materializer._prefetch",
        boom,
    )
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert main(["--verify-only", "--allow-acquire", "--repo-root", str(REPO)]) == 2
    assert main(["--verify-only", "--repo-root", str(REPO)]) == 0
