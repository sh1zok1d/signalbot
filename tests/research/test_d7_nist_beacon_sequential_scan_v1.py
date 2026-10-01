"""Offline control-flow tests for the beacon scan. No NIST fetch."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from scripts.research.d7_nist_beacon_sequential_scan_v1 import (
    MAX_CANDIDATES_PER_INVOCATION,
    VERIFIER_BLOB,
    VERIFIER_COMMIT,
    VERIFIER_CONTENT_SHA256,
    VERIFIER_PATH,
    VERIFIER_TREE,
    ScanStop,
    bind_resume_cursor,
    load_predecessor,
    merge_resume,
    parse_ledger,
    resume_invocation,
    scan,
)
from scripts.research.d7_nist_beacon_verifier_v1 import assess_pulse

ROOT = Path(__file__).resolve().parents[2]


def _body(pulse: dict) -> bytes:
    return json.dumps({"pulse": pulse}).encode("utf-8")


def _pulse(index: int, stamp: str, output: str, previous: str) -> dict:
    return {
        "certificateId": "cert",
        "chainIndex": 2,
        "listValues": [{"type": "previous", "value": previous}],
        "outputValue": output,
        "pulseIndex": index,
        "timeStamp": stamp,
    }


def _invalid(_pulse: dict, _certificate: bytes) -> dict:
    return {
        "VALID": False,
        "failure_code": "BEACON_SIGNATURE_REPRESENTATION_INVALID",
        "classification": "OBJECTIVELY_INVALID",
        "pkcs1_sha512_valid": False,
        "output_matches_serialization": True,
        "RSA_MODULUS_BYTES": 256,
        "SIGNATURE_BYTES": 512,
    }


def _valid(_pulse: dict, _certificate: bytes) -> dict:
    return {
        "VALID": True,
        "failure_code": None,
        "classification": "VALID",
        "pkcs1_sha512_valid": True,
        "output_matches_serialization": True,
        "RSA_MODULUS_BYTES": 256,
        "SIGNATURE_BYTES": 256,
    }


def test_verifier_blob_is_the_frozen_repair() -> None:
    import hashlib
    import subprocess

    raw = VERIFIER_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == VERIFIER_CONTENT_SHA256
    blob = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()
    assert blob == VERIFIER_BLOB
    tree = subprocess.check_output(["git", "rev-parse", f"{VERIFIER_COMMIT}^{{tree}}"], text=True).strip()
    committed = subprocess.check_output(
        ["git", "rev-parse", f"{VERIFIER_COMMIT}:scripts/research/d7_nist_beacon_verifier_v1.py"],
        text=True,
    ).strip()
    assert tree == VERIFIER_TREE
    assert committed == VERIFIER_BLOB
    text = (ROOT / "scripts/research/d7_nist_beacon_sequential_scan_v1.py").read_text(encoding="utf-8")
    assert "load_5m_bars" not in text
    assert "confirmatory_seed" not in text
    assert "SeedSequence" not in text
    assert MAX_CANDIDATES_PER_INVOCATION == 1000


def test_predecessor_is_pulse_1965184() -> None:
    pulse = load_predecessor()
    assert pulse["pulseIndex"] == 1965184
    assert pulse["timeStamp"] == "2026-10-01T07:10:00.000Z"


def test_first_valid_stops_without_another_pulse_fetch() -> None:
    predecessor = _pulse(1, "2026-10-01T07:09:59.000Z", "aa" * 64, "00" * 64)
    candidate = _pulse(2, "2026-10-01T07:11:00.000Z", "bb" * 64, "aa" * 64)
    seen: list[str] = []

    def fetch(url: str) -> bytes:
        seen.append(url)
        if "certificate" in url:
            return b"cert"
        if url.count("pulse/time/next") and seen.count(url) > 1:
            raise AssertionError("fetched a pulse after the first valid candidate")
        return _body(candidate)

    result = scan(predecessor, fetch, assess=_valid, require_frozen_predecessor=False)
    assert result["status"] == "SELECTED"
    assert result["SELECTED_CONFIRMATORY_BEACON"] == "2/2"
    assert result["valid_count"] == 1
    assert result["invalid_count"] == 0
    assert sum("pulse/time/next" in url for url in seen) == 1
    assert result["CONFIRMATORY_RNG_GENERATED"] is False


def test_invalid_then_404_does_not_select() -> None:
    raw = (ROOT / "docs/research/D7_CONFIRMATORY_BEACON_PULSE_V1.json").read_bytes()
    certificate = (ROOT / "docs/research/D7_CONFIRMATORY_BEACON_CERTIFICATE_V1.crt").read_bytes()
    pulse = json.loads(raw)["pulse"]
    previous_value = next(item["value"] for item in pulse["listValues"] if item["type"] == "previous")
    predecessor = _pulse(1965183, "2026-10-01T07:09:00.000Z", previous_value, "00" * 64)
    calls = {"pulse": 0}

    def fetch(url: str) -> bytes:
        if "certificate" in url:
            return certificate
        calls["pulse"] += 1
        if calls["pulse"] == 1:
            return raw
        raise ScanStop("BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE", kind="UNEXPECTED_404")

    result = scan(predecessor, fetch, assess=assess_pulse, require_frozen_predecessor=False)
    assert result["status"] == "BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE"
    assert result["SELECTED_CONFIRMATORY_BEACON"] == "NONE"
    assert result["valid_count"] == 0
    assert result["invalid_count"] == 1
    assert result["rows"][0]["final_status"] == "INVALID"
    assert result["rows"][0]["pulseIndex"] == 1965184
    assert result["rows"][0]["modulus_bytes"] == 256
    assert result["rows"][0]["signature_bytes"] == 512
    assert result["continuity_all_pass"] is True
    assert result["LAST_COMPLETELY_CLASSIFIED_CANDIDATE"] == "2/1965184"
    assert result["NEXT_REQUIRED_CANDIDATE"] == "chronological successor of 2/1965184"


def test_continuity_failure_stops() -> None:
    predecessor = _pulse(1, "2026-10-01T07:09:59.000Z", "aa" * 64, "00" * 64)
    candidate = _pulse(2, "2026-10-01T07:11:00.000Z", "bb" * 64, "cc" * 64)

    def fetch(url: str) -> bytes:
        if "certificate" in url:
            raise AssertionError("certificate fetch after continuity failure")
        return _body(candidate)

    result = scan(predecessor, fetch, assess=_valid, require_frozen_predecessor=False)
    assert result["status"] == "BEACON_CHAIN_CONTINUITY_FAILED"
    assert result["SELECTED_CONFIRMATORY_BEACON"] == "NONE"
    assert result["rows"][0]["continuity"] == "FAIL"
    assert result["valid_count"] == 0


def test_batch_limit_requests_continuation() -> None:
    predecessor = _pulse(10, "2026-10-01T07:09:59.000Z", "p0", "zz")
    pulse_calls = {"n": 0}

    def fetch(url: str) -> bytes:
        if "certificate" in url:
            return b"cert"
        pulse_calls["n"] += 1
        index = 10 + pulse_calls["n"]
        stamp = f"2026-10-01T07:{10 + pulse_calls['n']:02d}:00.000Z"
        previous = "p0" if pulse_calls["n"] == 1 else f"p{pulse_calls['n'] - 1}"
        return _body(_pulse(index, stamp, f"p{pulse_calls['n']}", previous))

    result = scan(
        predecessor,
        fetch,
        max_candidates=2,
        assess=_invalid,
        require_frozen_predecessor=False,
    )
    assert result["status"] == "D7_CONFIRMATORY_BEACON_SCAN_CONTINUATION_REQUIRED"
    assert result["invalid_count"] == 2
    assert result["valid_count"] == 0
    assert pulse_calls["n"] == 2
    assert result["NEXT_REQUIRED_CANDIDATE"] == "chronological successor of 2/12"
    assert result["SELECTED_CONFIRMATORY_BEACON"] == "NONE"


def _saved_scan():
    ledger_text = (ROOT / "docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.jsonl").read_text(encoding="utf-8")
    rows = parse_ledger(ledger_text)
    summary = json.loads((ROOT / "docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.json").read_text(encoding="utf-8"))
    cursor = (ROOT / "docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1_CURSOR.json").read_bytes()
    return ledger_text, rows, summary, cursor


def test_resume_binds_the_saved_cursor_without_reclassification() -> None:
    from datetime import datetime, timezone

    _text, rows, summary, cursor = _saved_scan()
    # The committed scan state advanced after this test was written; bind the
    # expectations to the committed ledger instead of a stale snapshot.
    last = rows[-1]["pulseIndex"]
    last_ts = json.loads(cursor)["pulse"]["timeStamp"]
    predecessor = bind_resume_cursor(summary, rows, cursor)
    assert predecessor["pulseIndex"] == last
    assert predecessor["timeStamp"] == last_ts
    seen: list[str] = []

    def fetch(url: str) -> bytes:
        seen.append(url)
        raise ScanStop("BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE", kind="UNEXPECTED_404")

    result = scan(predecessor, fetch, require_frozen_predecessor=False)
    merged = merge_resume(summary, rows, result)
    stamp = datetime.strptime(last_ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    millis = int(stamp.timestamp() * 1000)
    assert seen == [f"https://beacon.nist.gov/beacon/2.0/pulse/time/next/{millis}"]
    assert result["examined"] == 0
    assert result["status"] == "BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE"
    assert merged["resume_examined"] == 0
    assert merged["resume_retried_first"] == f"chronological successor of 2/{last}"
    assert merged["LAST_COMPLETELY_CLASSIFIED_CANDIDATE"] == f"2/{last}"
    assert merged["NEXT_REQUIRED_CANDIDATE"] == f"chronological successor of 2/{last}"
    assert merged["examined"] == len(rows)
    assert merged["scan_identity"] == "D7_CONFIRMATORY_BEACON_SCAN_V1"
    assert merged["scan_invocation"] == summary["scan_invocation"] + 1
    assert merged["CONFIRMATORY_RNG_GENERATED"] is False


def test_resume_appends_one_invalid_and_stops_on_404(tmp_path: Path) -> None:
    ledger_text, rows, summary, cursor = _saved_scan()
    out = tmp_path / "docs/research"
    out.mkdir(parents=True)
    (out / "D7_CONFIRMATORY_BEACON_SCAN_V1.jsonl").write_text(ledger_text, encoding="utf-8")
    (out / "D7_CONFIRMATORY_BEACON_SCAN_V1.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    (out / "D7_CONFIRMATORY_BEACON_SCAN_V1_CURSOR.json").write_bytes(cursor)
    previous = json.loads(cursor)["pulse"]["outputValue"]
    last = rows[-1]["pulseIndex"]
    last_ts = datetime.strptime(json.loads(cursor)["pulse"]["timeStamp"], "%Y-%m-%dT%H:%M:%S.%fZ")
    next_ts = (last_ts + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    successor = _pulse(last + 1, next_ts, "ab" * 64, previous)
    calls = {"pulse": 0}

    def fetch(url: str) -> bytes:
        if "certificate" in url:
            return b"cert"
        calls["pulse"] += 1
        if calls["pulse"] == 1:
            return _body(successor)
        raise ScanStop("BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE", kind="UNEXPECTED_404")

    resume_invocation(fetch, root=tmp_path, assess=_invalid)
    written = (out / "D7_CONFIRMATORY_BEACON_SCAN_V1.jsonl").read_text(encoding="utf-8")
    assert written.startswith(ledger_text)
    combined = parse_ledger(written)
    assert len(combined) == len(rows) + 1
    assert combined[len(rows) - 1] == rows[-1]
    assert combined[len(rows)]["sequence"] == len(rows) + 1
    assert combined[len(rows)]["pulseIndex"] == last + 1
    assert combined[len(rows)]["final_status"] == "INVALID"
    updated = json.loads((out / "D7_CONFIRMATORY_BEACON_SCAN_V1.json").read_text(encoding="utf-8"))
    assert updated["status"] == "BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE"
    assert updated["LAST_COMPLETELY_CLASSIFIED_CANDIDATE"] == f"2/{last + 1}"
    assert updated["NEXT_REQUIRED_CANDIDATE"] == f"chronological successor of 2/{last + 1}"
    assert updated["SELECTED_CONFIRMATORY_BEACON"] == "NONE"
    assert updated["resume_valid_count"] == 0
    assert updated["resume_invalid_count"] == 1
    assert updated["resume_continuity"] == "PASS"
    assert updated["D7_PRIMARY_EFFECT_COMPUTED"] is False
