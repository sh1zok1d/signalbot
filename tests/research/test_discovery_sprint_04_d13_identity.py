"""Outcome-blind D13 file-set identity tests. No scientific outcomes."""

from __future__ import annotations

import copy
import inspect
import json
import zipfile
from pathlib import Path

import pytest

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import d13_acquire as ACQ
from scripts.research.discovery_sprint_04 import d13_panel as P

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / C.D13_DOCS_REL
FREEZE_JSON = REPO / "docs/research/DISCOVERY_SPRINT_04_IMPLEMENTATION_FREEZE.json"

LEGAL_A = "data/spot/monthly/klines/AAAUSDT/1d/AAAUSDT-1d-2020-01.zip"
LEGAL_B = "data/spot/monthly/klines/BBBUSDT/1d/BBBUSDT-1d-2020-02.zip"
LEGAL_C = "data/spot/monthly/klines/CCCUSDT/1d/CCCUSDT-1d-2020-03.zip"
CSV_ROW = "1577836800000,1,1,1,1,1,1,42.0\n"


def _zip_bytes() -> bytes:
    from io import BytesIO

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("klines.csv", CSV_ROW)
    return buf.getvalue()


def _ledger_obj(key: str, sha: str, nbytes: int) -> dict:
    match = ACQ.OBJECT_RE.match(key)
    assert match is not None
    return {
        "key": key,
        "local_sha256": sha,
        "expected_sha256": sha,
        "byte_size": nbytes,
        "checksum_verification": "VERIFIED",
        "symbol": match.group(1),
        "month": match.group(2),
    }


def _write_panel(tmp: Path, keys: list[str], *, index_keys: list[str] | None = None) -> Path:
    docs = tmp / C.D13_DOCS_REL
    raw = tmp / C.D13_RAW_REL
    docs.mkdir(parents=True)
    payload = _zip_bytes()
    sha = C.sha256_bytes(payload)
    objects = []
    for key in keys:
        dest = raw / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        objects.append(_ledger_obj(key, sha, len(payload)))
    ledger = {"n_files": len(objects), "n_errors": 0, "objects": objects, "errors": []}
    (docs / "object_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    zips = list(keys if index_keys is None else index_keys)
    (docs / "object_key_index.json").write_text(
        json.dumps({"legal_zips": zips, "n_legal_zips": len(zips)}),
        encoding="utf-8",
    )
    return tmp


def _index_ledger(keys_index: list[str], keys_ledger: list[str]) -> tuple[dict, dict]:
    payload = _zip_bytes()
    sha = C.sha256_bytes(payload)
    ledger = {
        "n_files": len(keys_ledger),
        "objects": [_ledger_obj(k, sha, len(payload)) for k in keys_ledger],
    }
    index = {"legal_zips": list(keys_index)}
    return index, ledger


def test_subset_object_key_index_fails_closed():
    index, ledger = _index_ledger([LEGAL_A], [LEGAL_A, LEGAL_B])
    with pytest.raises(C.Sprint04IntegrityError, match=P.INDEX_LEDGER_KEYSET_MISMATCH):
        P.assert_index_ledger_keyset_equal(index, ledger)


def test_extra_object_key_index_key_fails_closed():
    index, ledger = _index_ledger([LEGAL_A, LEGAL_B, LEGAL_C], [LEGAL_A, LEGAL_B])
    with pytest.raises(C.Sprint04IntegrityError, match=P.INDEX_LEDGER_KEYSET_MISMATCH):
        P.assert_index_ledger_keyset_equal(index, ledger)


def test_same_count_different_membership_fails_closed():
    index, ledger = _index_ledger([LEGAL_A, LEGAL_C], [LEGAL_A, LEGAL_B])
    assert len(index["legal_zips"]) == len(ledger["objects"])
    with pytest.raises(C.Sprint04IntegrityError, match=P.INDEX_LEDGER_KEYSET_MISMATCH):
        P.assert_index_ledger_keyset_equal(index, ledger)


def test_reordered_identical_set_accepted():
    index, ledger = _index_ledger([LEGAL_B, LEGAL_A], [LEGAL_A, LEGAL_B])
    P.assert_index_ledger_keyset_equal(index, ledger)


def test_ledger_mutation_changes_snapshot_identity_and_fails_byte_verify(tmp_path: Path):
    repo = _write_panel(tmp_path, [LEGAL_A, LEGAL_B])
    ledger = P.load_object_ledger(repo=repo)
    original_digest = P.file_ledger_digest(ledger)
    enum = "0" * 64
    snap0 = P.snapshot_id(enumeration_digest=enum, ledger_digest=original_digest)
    mutated = copy.deepcopy(ledger)
    mutated["objects"][0]["local_sha256"] = "ab" * 32
    mutated["objects"][0]["expected_sha256"] = "ab" * 32
    mutated_digest = P.file_ledger_digest(mutated)
    assert mutated_digest != original_digest
    snap1 = P.snapshot_id(enumeration_digest=enum, ledger_digest=mutated_digest)
    assert snap1 != snap0
    (repo / C.D13_DOCS_REL / "object_ledger.json").write_text(
        json.dumps(mutated), encoding="utf-8"
    )
    with pytest.raises(C.SnapshotIdentityError, match="D13_LEDGER_MISMATCH"):
        P.verify_local_bytes_against_ledger(repo=repo)


def test_scientific_presence_loader_uses_ledger_bound_keys_not_index(tmp_path: Path):
    repo = _write_panel(tmp_path, [LEGAL_A, LEGAL_B], index_keys=[LEGAL_A])
    with pytest.raises(C.Sprint04IntegrityError, match=P.INDEX_LEDGER_KEYSET_MISMATCH):
        P.verify_index_ledger_keyset(repo=repo)
    panel = P.load_presence_panel(repo=repo)
    assert set(panel) == {"AAAUSDT", "BBBUSDT"}
    assert LEGAL_B.split("/")[4] == "BBBUSDT"


def test_presence_loader_does_not_read_object_key_index(tmp_path: Path):
    repo = _write_panel(tmp_path, [LEGAL_A, LEGAL_B])
    index_path = repo / C.D13_DOCS_REL / "object_key_index.json"
    index_path.write_text("not-json", encoding="utf-8")
    src = inspect.getsource(P.load_presence_panel)
    assert "object_key_index" not in src
    assert "legal_zips" not in src
    assert "scientific_file_keys" in src
    panel = P.load_presence_panel(repo=repo)
    assert set(panel) == {"AAAUSDT", "BBBUSDT"}
    index_path.unlink()
    panel2 = P.load_presence_panel(repo=repo)
    assert set(panel2) == {"AAAUSDT", "BBBUSDT"}


def test_scientific_file_keys_are_ledger_only(tmp_path: Path):
    repo = _write_panel(tmp_path, [LEGAL_B, LEGAL_A], index_keys=[LEGAL_C])
    keys = P.scientific_file_keys(repo=repo)
    assert keys == [LEGAL_B, LEGAL_A]
    src = inspect.getsource(P.scientific_file_keys)
    assert "object_key_index" not in src
    assert "load_object_ledger" in src


def test_duplicate_ledger_key_fails_closed():
    index, ledger = _index_ledger([LEGAL_A], [LEGAL_A, LEGAL_A])
    ledger["n_files"] = 2
    with pytest.raises(C.Sprint04IntegrityError, match="D13_DUPLICATE_LEDGER_KEY"):
        P.legal_zip_keys_from_ledger(ledger)


def test_protected_and_illegal_ledger_keys_fail_closed():
    payload = _zip_bytes()
    sha = C.sha256_bytes(payload)
    protected = {
        "n_files": 1,
        "objects": [
            {
                "key": "data/spot/monthly/klines/AAAUSDT/1d/AAAUSDT-1d-2025-01.zip",
                "local_sha256": sha,
                "expected_sha256": sha,
                "byte_size": 1,
                "checksum_verification": "VERIFIED",
                "symbol": "AAAUSDT",
                "month": "2025-01",
            }
        ],
    }
    with pytest.raises((ACQ.ProtectedYearRefused, C.ProtectedYearRefused)):
        P.legal_zip_keys_from_ledger(protected)
    illegal = {
        "n_files": 1,
        "objects": [
            {
                "key": "data/spot/monthly/klines/AAAUSDT/1d/AAAUSDT-1d-2019-11.zip",
                "local_sha256": sha,
                "expected_sha256": sha,
                "byte_size": 1,
                "checksum_verification": "VERIFIED",
                "symbol": "AAAUSDT",
                "month": "2019-11",
            }
        ],
    }
    with pytest.raises(C.Sprint04IntegrityError, match="D13_ILLEGAL_MONTH"):
        P.legal_zip_keys_from_ledger(illegal)


def test_ledger_n_files_must_equal_unique_key_count():
    index, ledger = _index_ledger([LEGAL_A, LEGAL_B], [LEGAL_A, LEGAL_B])
    ledger["n_files"] = 99
    with pytest.raises(C.Sprint04IntegrityError, match="D13_LEDGER_COUNT_MISMATCH"):
        P.legal_zip_keys_from_ledger(ledger)


def test_frozen_index_ledger_set_and_snapshot_id_unchanged():
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    index = json.loads((DOCS / "object_key_index.json").read_text(encoding="utf-8"))
    ledger = json.loads((DOCS / "object_ledger.json").read_text(encoding="utf-8"))
    prefixes = json.loads((DOCS / "symbol_prefixes.json").read_text(encoding="utf-8"))
    P.assert_index_ledger_keyset_equal(index, ledger)
    digest = P.file_ledger_digest(ledger)
    snap = P.snapshot_id(
        enumeration_digest=prefixes["listing_digest"],
        ledger_digest=digest,
    )
    assert digest == freeze["D13_FILE_LEDGER_DIGEST"]
    assert snap == freeze["D13_SNAPSHOT_ID"]
    assert snap == "fdd698c66ce894ba981665c1b4bd5661e7a13b275368ad89f532df9bcc455acd"
    assert digest == "fc38ea13756d7da9a8500420adcb8d918bcd7632367b0d7026fd31a1636c56cd"
    assert freeze["D13_N"] == 82
    assert freeze["D13_NO_POST_T_CLOSE_SELECTED_N"] == 0
    assert freeze["RED_TEAM"]["F20"]["STATUS"] == "CONFIRMED_AND_FIXED_PRE_OUTCOME"
